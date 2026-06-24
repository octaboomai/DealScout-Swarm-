import streamlit as st
import sys
import os
import PyPDF2
import json
import re
import time

# Ensure swarm_engine and auth are in path
sys.path.append(os.path.dirname(__file__))
from swarm_engine import run_swarm
import auth

# ─────────────────────────────────────────────────────────────────────────────
# 1. AGENCY CONFIGURATION (WhatsApp + UPI Method)
# ─────────────────────────────────────────────────────────────────────────────
AGENCY_NAME = "DealScout Intelligence™"
WHATSAPP_NUMBER = "919876543210" 
UPGRADE_MESSAGE = "Hi! I want to upgrade to DealScout Pro Unlimited Access. Please share the payment details."
WHATSAPP_LINK = f"https://wa.me/{WHATSAPP_NUMBER}?text={UPGRADE_MESSAGE.replace(' ', '%20')}"

st.set_page_config(page_title=AGENCY_NAME, layout="centered", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────────────────────────────────────
# 2. PREMIUM UX STYLING (Next.js / Tailwind Emulation in Streamlit)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Hide Streamlit Junk */
#MainMenu, header, footer, [data-testid="stToolbar"] { display: none !important; }
html, body, [data-testid="stAppViewContainer"] { background: #020617 !important; font-family: 'Inter', sans-serif !important; color: #f8fafc; }
[data-testid="stMain"] > div { max-width: 850px !important; margin: 0 auto !important; padding: 2rem !important; }

/* Header Formatting */
.agency-header { display: flex; align-items: center; gap: 12px; padding: 20px 0; border-bottom: 1px solid #1e293b; margin-bottom: 30px; }
.agency-logo { background: linear-gradient(135deg, #34d399, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 28px; font-weight: 700; }
.agency-sub { color: #94a3b8; font-size: 14px; font-weight: 500; }

/* Dashboard Cards */
.ds-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
.ds-card-title { display: flex; align-items: center; gap: 8px; color: #f8fafc; font-size: 18px; font-weight: 600; border-bottom: 1px solid #1e293b; padding-bottom: 12px; margin-bottom: 16px; margin-top: 0;}
.ds-icon { font-size: 20px; }

/* Typography inside Cards */
.ds-text { color: #cbd5e1; font-size: 16px; line-height: 1.7; margin: 0; }

/* Data Rows (Key Metrics) */
.ds-metric-row { display: flex; justify-content: space-between; align-items: center; background: #020617; border: 1px solid #1e293b; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; }
.ds-metric-label { color: #94a3b8; font-weight: 500; font-size: 14px; }
.ds-metric-value { color: #f8fafc; font-weight: 700; font-size: 18px; display: flex; gap: 12px; align-items: center;}
.ds-trend-up { color: #34d399; font-size: 14px; }
.ds-trend-down { color: #f43f5e; font-size: 14px; }
.ds-trend-flat { color: #94a3b8; font-size: 14px; }

/* Risk Matrix */
.ds-risk-row { display: flex; justify-content: space-between; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid #1e293b; }
.ds-risk-row:last-child { border-bottom: none; }
.ds-risk-title { color: #e2e8f0; font-weight: 500; font-size: 15px; }
.ds-badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
.ds-badge-high { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); box-shadow: 0 0 10px rgba(244, 63, 94, 0.2); }
.ds-badge-medium { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
.ds-badge-low { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }

/* Inputs & Buttons */
[data-testid="stChatInput"] { background: #0f172a !important; border: 1px solid #334155 !important; }
[data-testid="stChatInput"] textarea { color: #f8fafc !important; }
.stButton>button { background: #34d399 !important; color: #020617 !important; border: none !important; font-weight: 600 !important; border-radius: 8px !important; transition: 0.2s; }
.stButton>button:hover { background: #10b981 !important; }
.whatsapp-btn { display: block; background: #25D366; color: white !important; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center; margin: 10px 0; font-size: 15px; transition: 0.2s;}
.whatsapp-btn:hover { background: #1ebe57; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(37, 211, 102, 0.3);}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 3. HELPER FUNCTIONS (JSON Parser)
# ─────────────────────────────────────────────────────────────────────────────
def extract_json_from_text(text: str):
    """Fallback parser in case the AI wraps JSON in markdown blocks like ```json ... ```"""
    try:
        # First, try to parse it directly
        return json.loads(text)
    except json.JSONDecodeError:
        # If it fails, search for a JSON object structure
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
    return None

def render_dashboard(data: dict):
    """Converts the JSON Dictionary into our beautiful Streamlit UI HTML"""
    
    html = f"""
    <div style="margin-bottom: 40px;">
        <h2 style="color: #f8fafc; font-size: 26px; font-weight: 700; margin-bottom: 24px;">
            {data.get('title', 'Intelligence Report')}
        </h2>

        <!-- Executive Summary Card -->
        <div class="ds-card">
            <h3 class="ds-card-title"><span class="ds-icon">💼</span> Executive Bottom Line</h3>
            <p class="ds-text">{data.get('executive_summary', 'No summary provided.')}</p>
        </div>
    """

    # Create a 2-column layout using flexbox inside HTML
    html += '<div style="display: flex; gap: 24px; flex-wrap: wrap;">'

    # Market Data Card
    html += '<div class="ds-card" style="flex: 1; min-width: 300px;"><h3 class="ds-card-title"><span class="ds-icon">📊</span> Key Data Points</h3>'
    metrics = data.get('market_data', [])
    if not isinstance(metrics, list):
        metrics = []
    for m in metrics:
        if isinstance(m, dict):
            label = str(m.get('label', 'Metric'))
            val = str(m.get('value', 'N/A'))
            trend = str(m.get('trend') or '')
            trend_class = "ds-trend-up" if "+" in trend else "ds-trend-down" if "-" in trend else "ds-trend-flat"
            
            html += f"""
            <div class="ds-metric-row">
                <span class="ds-metric-label">{label}</span>
                <span class="ds-metric-value">{val} <span class="{trend_class}">{trend}</span></span>
            </div>
            """
        else:
            html += f'<div class="ds-metric-row"><span class="ds-metric-label">{m}</span></div>'
    html += '</div>'

    # Risk Matrix Card
    html += '<div class="ds-card" style="flex: 1; min-width: 300px;"><h3 class="ds-card-title"><span class="ds-icon">🚨</span> Risk Matrix</h3>'
    risks = data.get('risk_matrix', [])
    if not isinstance(risks, list):
        risks = []
    for r in risks:
        if isinstance(r, dict):
            risk_text = str(r.get('risk', 'Unknown Risk'))
            sev = str(r.get('severity') or 'Medium')
            badge_class = "ds-badge-high" if sev.lower() == "high" else "ds-badge-low" if sev.lower() == "low" else "ds-badge-medium"
            
            html += f"""
            <div class="ds-risk-row">
                <span class="ds-risk-title">{risk_text}</span>
                <span class="ds-badge {badge_class}">{sev.upper()}</span>
            </div>
            """
        else:
            html += f'<div class="ds-risk-row"><span class="ds-risk-title">{r}</span></div>'
    html += '</div>'

    html += '</div></div>' # Close flex container and wrapper
    
    # Strip newlines + their leading whitespace: a blank line followed by 4+ spaces of
    # indentation makes Streamlit's markdown parser treat the rest as a literal code block
    # instead of HTML. HTML rendering doesn't care about these newlines anyway.
    html = re.sub(r'\n\s*', '', html)
    st.markdown(html, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 4. AUTHENTICATION GATE (Supabase: real per-user accounts)
# ─────────────────────────────────────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown(f"""
    <div style="text-align: center; margin-top: 8vh; margin-bottom: 30px;">
        <h1 style="font-size: 3rem; margin-bottom: 0;">DealScout <span style="color: #34d399;">Pro</span></h1>
        <p style="color: #94a3b8; font-size: 1.1rem;">Autonomous B2B Intelligence & Risk Mitigation Platform</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔑 Log In", "🆕 Sign Up"])

    with tab_login:
        login_email = st.text_input("Email", key="login_email")
        login_pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log In", use_container_width=True, key="login_btn"):
            try:
                resp = auth.sign_in(login_email, login_pw)
                st.session_state.user = {"id": resp.user.id, "email": resp.user.email}
                st.session_state.access_token = resp.session.access_token
                st.session_state.refresh_token = resp.session.refresh_token
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_signup:
        signup_email = st.text_input("Email", key="signup_email")
        signup_pw = st.text_input("Password (min 6 characters)", type="password", key="signup_pw")
        if st.button("Create Account", use_container_width=True, key="signup_btn"):
            try:
                auth.sign_up(signup_email, signup_pw)
                st.success("Account created! Check your email to confirm it, then log in on the other tab.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")

    st.stop()

# Logged in — refresh subscription + usage from Supabase every run, so tokens
# running out or a code being redeemed elsewhere is always reflected.
user = st.session_state.user
subscription = auth.get_or_create_subscription(user["id"], user["email"])
st.session_state.access_tier = auth.get_active_tier(subscription)
st.session_state.usage = auth.get_usage(user["id"])

# ─────────────────────────────────────────────────────────────────────────────
# 5. SECURE DEAL ROOM (Sidebar)
# ─────────────────────────────────────────────────────────────────────────────
if "document_context" not in st.session_state:
    st.session_state.document_context = ""
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.markdown(f"### 👤 {user['email']}")
    st.markdown(f"**Tier:** {st.session_state.access_tier.upper()}")

    if st.session_state.access_tier == "pro":
        balance = subscription.get("token_balance") or 0
        st.caption(f"Pro access — {balance:,} tokens remaining")
        with st.expander("🎁 Top Up Tokens"):
            redeem_code = st.text_input("Code emailed to you after payment:", key="redeem_code")
            if st.button("Add Tokens", use_container_width=True, key="redeem_btn"):
                ok, msg = auth.redeem_pro_code(user["id"], redeem_code)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        usage = st.session_state.usage
        prompts_left = max(auth.FREE_PROMPT_LIMIT - usage.get("prompts_in_window", 0), 0)
        pdfs_left = max(auth.FREE_PDF_LIMIT - usage.get("pdf_uploads_in_window", 0), 0)
        if prompts_left == 0:
            mins = auth.minutes_until_reset(usage)
            st.caption(f"Free tier — 0 prompts left, resets in {mins} min · {pdfs_left} PDF upload(s) left this window")
        else:
            st.caption(f"Free tier — {prompts_left} prompt(s) and {pdfs_left} PDF upload(s) left (resets every {auth.RATE_LIMIT_WINDOW_HOURS}h)")
        st.markdown(f'<a href="{WHATSAPP_LINK}" target="_blank" class="whatsapp-btn">⚡ Buy Pro Tokens</a>', unsafe_allow_html=True)

        with st.expander("🎁 Redeem Pro Code"):
            redeem_code = st.text_input("Code emailed to you after payment:", key="redeem_code")
            if st.button("Activate Pro", use_container_width=True, key="redeem_btn"):
                ok, msg = auth.redeem_pro_code(user["id"], redeem_code)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.divider()
    st.markdown("### 📂 Deal Room Vault")
    st.markdown("<p style='color: #94a3b8; font-size: 13px;'>Upload PDF for RAG Analysis.</p>", unsafe_allow_html=True)

    pdf_blocked = st.session_state.access_tier == "free" and not auth.can_upload_pdf_free(st.session_state.usage)
    if pdf_blocked:
        mins = auth.minutes_until_reset(st.session_state.usage)
        st.warning(f"Free PDF upload limit reached for this window. Resets in {mins} min, or pay via WhatsApp to reset now, or upgrade to Pro.")
        st.markdown(f'<a href="{WHATSAPP_LINK}" target="_blank" class="whatsapp-btn">💬 Reset Now (₹50)</a>', unsafe_allow_html=True)
    else:
        uploaded_file = st.file_uploader("", type="pdf")
        # Guard against re-counting the same upload on every script rerun
        if uploaded_file is not None and uploaded_file.name != st.session_state.get("_last_pdf_name"):
            try:
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text()])
                st.session_state.document_context = text[:15000]
                st.session_state._last_pdf_name = uploaded_file.name
                if st.session_state.access_tier == "free":
                    auth.record_pdf_used(user["id"])
                st.success("✅ Securely Loaded")
            except Exception as e:
                st.error(f"Error reading PDF: {e}")

    st.divider()
    if st.button("🔒 Log Out", use_container_width=True):
        auth.sign_out(st.session_state.get("access_token", ""), st.session_state.get("refresh_token", ""))
        for key in ["user", "access_token", "refresh_token", "access_tier", "usage",
                    "document_context", "history", "_last_pdf_name"]:
            st.session_state.pop(key, None)
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# 6. MAIN DASHBOARD UI
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="agency-header">
    <div style="font-size: 32px;">⚡</div>
    <div>
        <div class="agency-logo">{AGENCY_NAME}</div>
        <div class="agency-sub">Multi-Agent Swarm Active • Awaiting Instructions</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Render Historical Reports
for item in st.session_state.history:
    st.markdown(f"<p style='color: #94a3b8;'><strong>Prompt:</strong> {item['prompt']}</p>", unsafe_allow_html=True)
    
    # Try parsing history as JSON
    parsed = extract_json_from_text(item['output'])
    if parsed and isinstance(parsed, dict):
        render_dashboard(parsed)
    else:
        # Fallback to standard text if the AI didn't output JSON
        st.markdown(f"<div class='ds-card'><div class='ds-text'>{item['output']}</div></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 7. CHAT INPUT & THEATER OF WORK
# ─────────────────────────────────────────────────────────────────────────────
if prompt := st.chat_input("e.g. Give me a deep dive on Ola Electric vs Ather Energy..."):

    if st.session_state.access_tier == "free" and not auth.can_generate_prompt(st.session_state.usage):
        mins = auth.minutes_until_reset(st.session_state.usage)
        st.warning(f"Free prompt limit reached for this window. Resets in {mins} min, or pay via WhatsApp to reset now, or upgrade to Pro.")
        st.markdown(f'<a href="{WHATSAPP_LINK}" target="_blank" class="whatsapp-btn">💬 Reset Now (₹50)</a>', unsafe_allow_html=True)
        st.stop()

    st.markdown(f"<p style='color: #f8fafc; font-size: 18px; margin-top: 20px;'><strong>Query:</strong> {prompt}</p>", unsafe_allow_html=True)

    full_prompt = prompt
    if st.session_state.document_context != "":
         full_prompt = f"DOCUMENT CONTEXT:\n{st.session_state.document_context}\n\nUSER REQUEST: {prompt}"

    # Theater of Work (Streamlit's version of the loading sequence)
    with st.status("Initializing Swarm Protocol...", expanded=True) as status:
        st.write("🔄 Engagement Manager analyzing request...")
        time.sleep(0.5)
        st.write("🌐 Market Analyst gathering live web/financial data...")
        
        try:
            # THIS IS WHERE IT CALLS YOUR PYTHON SCRIPT
            result = run_swarm(full_prompt, tier=st.session_state.access_tier)
            final_output = result.get("final_answer", "Error: No answer provided.")
            tokens_used = result.get("tokens_used", 0)
            if st.session_state.access_tier == "free":
                auth.record_prompt_used(user["id"])
            else:
                auth.spend_tokens(user["id"], tokens_used)
        except Exception as e:
            final_output = f"⚠️ Swarm Error: {e}"
        
        st.write("🧠 Strategy Associate drafting memo...")
        time.sleep(0.5)
        st.write("🛡️ Risk Director auditing claims...")
        time.sleep(0.5)
        st.write("✅ Managing Partner structuring final JSON payload...")
        status.update(label="Intelligence Compiled Successfully", state="complete", expanded=False)

    # UI Rendering
    parsed_json = extract_json_from_text(final_output)
    
    if parsed_json and isinstance(parsed_json, dict):
        # Successfully parsed JSON, render the beautiful dashboard
        render_dashboard(parsed_json)
    else:
        # Fallback if the AI messes up the format
        st.warning("Data format error: Displaying raw intelligence.")
        st.markdown(f"<div class='ds-card'><div class='ds-text'>{final_output}</div></div>", unsafe_allow_html=True)

    # Save to history
    st.session_state.history.append({"prompt": prompt, "output": final_output})
