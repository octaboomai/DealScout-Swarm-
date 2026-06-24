"""
auth.py — Supabase-backed accounts, token billing, and rate limiting for DealScout.

Two Supabase clients are used deliberately:
  - anon client  (SUPABASE_ANON_KEY)          -> ONLY for sign_up/sign_in/sign_out.
  - admin client (SUPABASE_SERVICE_ROLE_KEY)  -> ALL subscriptions/usage table access.
(If your Supabase project shows "publishable"/"secret" keys instead of the
older "anon"/"service_role" labels, they're drop-in replacements — use the
publishable key as SUPABASE_ANON_KEY and the secret key as
SUPABASE_SERVICE_ROLE_KEY.)

The admin key bypasses Row Level Security. It must only ever live in
Streamlit secrets / server-side environment variables — never send it to the
browser, never put it in a query string, never log it.

BILLING MODEL
  Pro   : a token bucket. Buying access means buying a number of tokens
          (you choose the amount per customer — there's no fixed plan size).
          Each report deducts the tokens it actually cost to generate.
          Once token_balance hits 0, the account drops back to Free
          behavior until topped up.
  Free  : a rolling rate limit, not a lifetime cap. 3 prompts and 2 PDF
          uploads per rolling 4-hour window; the window auto-resets once
          4 hours have passed since it started.
"""

import os
import secrets
import string
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

FREE_PROMPT_LIMIT = 3
FREE_PDF_LIMIT = 2
RATE_LIMIT_WINDOW_HOURS = 4


# ─────────────────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────────────────
def get_anon_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


def get_admin_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ─────────────────────────────────────────────────────────────────────────
# Auth — sign up / log in / log out
# ─────────────────────────────────────────────────────────────────────────
def sign_up(email: str, password: str):
    """Raises on failure (e.g. weak password, email already registered).
    By default Supabase requires the user to click a confirmation link before
    they can log in — disable 'Confirm email' under Authentication settings
    in your Supabase dashboard if you want frictionless signup instead."""
    client = get_anon_client()
    return client.auth.sign_up({"email": email, "password": password})


def sign_in(email: str, password: str):
    """Raises on bad credentials. Returns an AuthResponse with .user and .session."""
    client = get_anon_client()
    return client.auth.sign_in_with_password({"email": email, "password": password})


def sign_out(access_token: str, refresh_token: str):
    """Best-effort server-side session invalidation. The caller is responsible
    for clearing st.session_state regardless of whether this succeeds."""
    try:
        client = get_anon_client()
        client.auth.set_session(access_token, refresh_token)
        client.auth.sign_out()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# Subscription state
# ─────────────────────────────────────────────────────────────────────────
def get_or_create_subscription(user_id: str, email: str) -> dict:
    """Fetch this user's subscription row, creating a fresh free-tier row +
    usage row on their very first login."""
    admin = get_admin_client()
    res = admin.table("subscriptions").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    new_row = {"user_id": user_id, "email": email, "plan": "free", "token_balance": 0}
    admin.table("subscriptions").insert(new_row).execute()
    admin.table("usage").insert({"user_id": user_id}).execute()
    return new_row


def get_active_tier(subscription: dict) -> str:
    """'pro' only if plan == 'pro' AND there are tokens left to spend.
    Hitting zero tokens drops the account back to Free automatically —
    no expiry date to track, no manual revocation needed."""
    if subscription.get("plan") == "pro" and (subscription.get("token_balance") or 0) > 0:
        return "pro"
    return "free"


# ─────────────────────────────────────────────────────────────────────────
# Pro code: issuance (admin side) + redemption (user side)
# ─────────────────────────────────────────────────────────────────────────
def generate_pro_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "DSPRO-" + "".join(secrets.choice(chars) for _ in range(8))


def issue_pro_code(email: str, token_amount: int) -> dict | None:
    """ADMIN SIDE — call after manually confirming a UPI/WhatsApp payment.
    token_amount is whatever you and the customer agreed on — there's no
    fixed bundle size baked in here. Works the same for a first purchase
    or a top-up on an existing Pro account (tokens add to whatever balance
    is already there). Does NOT email it — pair with send_pro_code_email()."""
    admin = get_admin_client()
    existing = admin.table("subscriptions").select("user_id").eq("email", email).execute()
    if not existing.data:
        return None  # this email hasn't signed up / logged in yet
    code = generate_pro_code()
    admin.table("subscriptions").update({
        "pro_code": code,
        "pending_tokens": token_amount,
    }).eq("email", email).execute()
    return {"code": code, "token_amount": token_amount}


def redeem_pro_code(user_id: str, entered_code: str) -> tuple[bool, str]:
    """USER SIDE — called from the app when they paste in the code they were emailed."""
    admin = get_admin_client()
    res = admin.table("subscriptions").select("*").eq("user_id", user_id).execute()
    if not res.data:
        return False, "No account found — please log in again."
    row = res.data[0]
    if not row.get("pro_code"):
        return False, "No Pro code is pending on this account yet — pay via WhatsApp first."
    if row["pro_code"].strip().upper() != entered_code.strip().upper():
        return False, "That code doesn't match what we issued for this account."
    tokens = row.get("pending_tokens") or 0
    admin.rpc("add_tokens", {"uid": user_id, "amount": tokens}).execute()
    admin.table("subscriptions").update({
        "plan": "pro",
        "pro_code": None,        # one-time use; clear it so it can't be redeemed twice
        "pending_tokens": None,
    }).eq("user_id", user_id).execute()
    return True, f"{tokens:,} tokens added! You're on Pro until they run out."


# ─────────────────────────────────────────────────────────────────────────
# Token spending (Pro)
# ─────────────────────────────────────────────────────────────────────────
def spend_tokens(user_id: str, amount: int):
    if amount > 0:
        get_admin_client().rpc("deduct_tokens", {"uid": user_id, "amount": amount}).execute()


# ─────────────────────────────────────────────────────────────────────────
# Free-tier rolling rate limit
# ─────────────────────────────────────────────────────────────────────────
def get_usage(user_id: str) -> dict:
    """Fetches the usage row, auto-resetting the 4-hour window server-side
    if it has expired, so the counters the caller sees are always current."""
    admin = get_admin_client()
    res = admin.table("usage").select("*").eq("user_id", user_id).execute()
    if not res.data:
        admin.table("usage").insert({"user_id": user_id}).execute()
        res = admin.table("usage").select("*").eq("user_id", user_id).execute()
    row = res.data[0]
    window_start = datetime.fromisoformat(row["window_start"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - window_start >= timedelta(hours=RATE_LIMIT_WINDOW_HOURS):
        admin.rpc("reset_usage_window", {"uid": user_id}).execute()
        row = {**row, "window_start": datetime.now(timezone.utc).isoformat(),
               "prompts_in_window": 0, "pdf_uploads_in_window": 0}
    return row


def can_generate_prompt(usage: dict) -> bool:
    return usage.get("prompts_in_window", 0) < FREE_PROMPT_LIMIT


def can_upload_pdf_free(usage: dict) -> bool:
    return usage.get("pdf_uploads_in_window", 0) < FREE_PDF_LIMIT


def minutes_until_reset(usage: dict) -> int:
    window_start = datetime.fromisoformat(usage["window_start"].replace("Z", "+00:00"))
    reset_at = window_start + timedelta(hours=RATE_LIMIT_WINDOW_HOURS)
    remaining = reset_at - datetime.now(timezone.utc)
    return max(int(remaining.total_seconds() // 60), 0)


def record_prompt_used(user_id: str):
    get_admin_client().rpc("increment_prompts_in_window", {"uid": user_id}).execute()


def record_pdf_used(user_id: str):
    get_admin_client().rpc("increment_pdfs_in_window", {"uid": user_id}).execute()


def grant_bonus_reset(email: str) -> bool:
    """ADMIN SIDE — call after confirming a ₹50 'skip the wait' payment.
    Immediately resets that user's 4-hour window, giving them a fresh 3
    prompts / 2 uploads right now instead of waiting out the clock."""
    admin = get_admin_client()
    sub = admin.table("subscriptions").select("user_id").eq("email", email).execute()
    if not sub.data:
        return False
    admin.rpc("reset_usage_window", {"uid": sub.data[0]["user_id"]}).execute()
    return True


# ─────────────────────────────────────────────────────────────────────────
# Email delivery (Resend) — sending the redeem code after payment confirmation
# ─────────────────────────────────────────────────────────────────────────
def send_pro_code_email(to_email: str, code: str, token_amount: int) -> bool:
    """Returns True if Resend accepted the send. Requires RESEND_API_KEY and
    a verified sending domain in your Resend dashboard (the test sender only
    delivers to your own Resend account email)."""
    import resend
    resend.api_key = os.environ["RESEND_API_KEY"]
    html = f"""
        <p>Hi,</p>
        <p>Your DealScout Pro code, adding <strong>{token_amount:,} tokens</strong>
        to your account, is:</p>
        <p style="font-size:20px; font-weight:700; letter-spacing:2px;">{code}</p>
        <p>Enter this code on the "Redeem Pro Code" screen after logging in to activate it.</p>
        <p>— DealScout Intelligence™</p>
    """
    try:
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM_EMAIL", "DealScout <onboarding@resend.dev>"),
            "to": [to_email],
            "subject": "Your DealScout Pro code",
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[RESEND ERROR] {e}")
        return False
