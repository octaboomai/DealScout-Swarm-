import streamlit as st
import sys
import os
import json
import PyPDF2
import bcrypt # For secure password hashing

sys.path.append(os.path.dirname(__file__))
from swarm_engine import run_swarm

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION & HELPERS
# ─────────────────────────────────────────────────────────────────────────────
AGENCY_NAME = "DealScout Intelligence™"
USERS_DB_FILE = "users.json"
PRO_UNLOCK_CODE = "DEALSCOUT_PRO_2024" # Users get this after paying via Stripe

# Stripe Payment Link (Create this in your Stripe Dashboard -> Payment Links)
# Example: https://buy.stripe.com/test_00abc123xyz
STRIPE_PAYMENT_LINK = "https://buy.stripe.com/REPLACE_WITH_YOUR_STRIPE_LINK" 

st.set_page_config(page_title=AGENCY_NAME, layout="centered", initial_sidebar_state="expanded")

def load_users():
    if not os.path.exists(USERS_DB_FILE):
        return {}
    with open(USERS_DB_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

# ─────────────────────────────────────────────────────────────────────────────
# 2. PREMIUM UI STYLING 
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
html, body, [data-testid="stAppViewContainer"] { background: #09090b !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stMain"] > div { max-width: 800px !important; margin: 0 auto !important; padding: 0 24px !important; }
.agency-header { text-align: center; padding: 48px 0 32px; border-bottom: 1px solid #27272a; margin-bottom: 32px; }
.agency-logo { font-size: 40px; margin-bottom: 8px; }
.agency-title { font-size: 22px; font-weight: 600; color: #fafafa; letter-spacing: -0.5px; margin: 0; }
.agency-sub { font-size: 13px; color: #71717a; margin-top: 6px; text-transform: uppercase; letter-spacing: 1px; }
[data-testid="stChatMessage"] { background: transparent !important; border: none !important; padding: 0 !important; margin-bottom: 32px !important; gap: 12px !important; }
[data-testid="chatAvatarIcon-user"] { background: #27272a !important; color: #a1a1aa !important; width: 28px !important; height: 28px !important; border-radius: 4px !important; }
[data-testid="chatAvatarIcon-assistant"] { background: #f59e0b !important; color: #000 !important; width: 28px !important; height: 28px !important; border-radius: 4px !important; }
[data-testid="stMarkdownContainer"] p { font-size: 15px !important; line-height: 1.8 !important; color: #d4d4d8 !important; margin: 0 0 8px !important; }
.route-pill { display: inline-flex; align-items: center; gap: 6px; background: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 4px 12px; font-size: 11px; color: #71717a; margin-bottom: 16px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
.route-dot { width: 6px; height: 6px; border-radius: 50%; background: #f59e0b; display: inline-block; }
.exec-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid #27272a; }
.exec-label { font-size: 12px; font-weight: 600; color: #f59e0b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
[data-testid="stChatInput"] { background: #18181b !important; border: 1px solid #27272a !important; border-radius: 8px !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; color: #e4e4e7 !important; font-size: 15px !important; }
.stButton>button { background: #f59e0b !important; color: #000 !important; border: none !important; font-weight: 600 !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 3. AUTHENTICATION & MONETIZATION GATE
# ─────────────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = None

if not st.session_state.authenticated:
    st.markdown(f"""
    <div class="agency-header">
        <div class="agency-logo">📊</div>
        <p class="agency-title">{AGENCY_NAME}</p>
        <p class="agency-sub">Autonomous B2B Intelligence & Risk Mitigation</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            users = load_users()
            if email in users and bcrypt.checkpw(password.encode('utf-8'), users[email]["password"].encode('utf-8')):
                st.session_state.authenticated = True
                st.session_state.user_email = email
                st.rerun()
            else:
                st.error("Invalid email or password.")

    with tab2:
        new_email = st.text_input("Work Email", key="signup_email")
        new_name = st.text_input("Full Name", key="signup_name")
        new_pass = st.text_input("Create Password", type="password", key="signup_pass")
        if st.button("Create Free Account"):
            if not new_email or not new_pass:
                st.warning("Please fill out all fields.")
            else:
                users = load_users()
                if new_email in users:
                    st.error("Email already registered.")
                else:
                    hashed_pw = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    users[new_email] = {
                        "name": new_name,
                        "password": hashed_pw,
                        "tier": "free",
                        "reports_generated": 0,
                        "max_free_reports": 3
                    }
                    save_users(users)
                    st.session_state.authenticated = True
                    st.session_state.user_email = new_email
                    st.rerun()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# 4. LOGGED IN DASHBOARD & PDF VAULT
# ─────────────────────────────────────────────────────────────────────────────
users = load_users()
user_data = users[st.session_state.user_email]

# Pro Upgrade Logic (Sidebar)
with st.sidebar:
    st.markdown(f"**👤 {user_data['name']}**")
    st.markdown(f"Tier: `{user_data['tier'].upper()}`")
    
    if user_data['tier'] == 'free':
        reports_left = user_data['max_free_reports'] - user_data['reports_generated']
        st.warning(f"🆓 Free Reports Left: **{reports_left}**")
        
        st.markdown("---")
        st.markdown("**Upgrade to Pro for Unlimited Reports**")
        if st.button("🚀 Buy Pro Access ($149/mo)"):
            st.markdown(f'<meta http-equiv="refresh" content="0; url={STRIPE_PAYMENT_LINK}">', unsafe_allow_html=True)
        
        pro_code = st.text_input("Enter Pro Code from Stripe receipt:")
        if st.button("Unlock Pro"):
            if pro_code == PRO_UNLOCK_CODE:
                users[st.session_state.user_email]['tier'] = 'pro'
                save_users(users)
                st.success("Upgraded to Pro! Please refresh.")
                st.rerun()
            elif pro_code:
                st.error("Invalid Pro Code.")
    else:
        st.success("♾️ Unlimited Pro Access")

    st.divider()
    st.markdown("<h3 style='color: #fafafa; font-weight: 600;'>📂 Secure Deal Room</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #71717a; font-size: 13px;'>Upload Pitch Decks, 10-Ks.</p>", unsafe_allow_html=True)
    
    if "document_context" not in st.session_state:
        st.session_state.document_context = ""

    uploaded_file = st.file_uploader("", type="pdf")
    if uploaded_file is not None:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text()])
            if len(text) > 12000: text = text[:12000] + "\n\n...[Document Truncated for Swarm Memory]..."
            st.session_state.document_context = text
            st.success("✅ Securely Loaded")
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    st.divider()
    if st.button("🔒 Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN CHAT INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="agency-header">
    <div class="agency-logo">📊</div>
    <p class="agency-title">{AGENCY_NAME}</p>
    <p class="agency-sub">Engagement Active · 5 Agents Standing By</p>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("route"):
            route_text = " ➔ ".join(msg["route"])
            st.markdown(f'<div class="route-pill"><span class="route-dot"></span>{route_text}</div>', unsafe_allow_html=True)
        
        content = msg["content"]
        if "EXECUTIVE BOTTOM LINE:" in content:
            content = content.replace("🎯 EXECUTIVE BOTTOM LINE:", "<div class='exec-section'><div class='exec-label'>🎯 Executive Bottom Line</div>")
            content = content.replace("🧠 STRATEGIC CONTEXT:", "</div><div class='exec-section'><div class='exec-label'>🧠 Strategic Context</div>")
            content = content.replace("🚨 RISK FACTORS:", "</div><div class='exec-section'><div class='exec-label'>🚨 Risk Factors</div>")
            content = content.replace("📊 KEY DATA POINTS:", "</div><div class='exec-section'><div class='exec-label'>📊 Key Data Points</div>")
            content += "</div>"
            st.markdown(content, unsafe_allow_html=True)
        else:
            st.markdown(content)

# ─────────────────────────────────────────────────────────────────────────────
# 6. CHAT INPUT & FREEMIUM ENFORCEMENT
# ─────────────────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Initiate intelligence gathering..."):
    # Check Free Tier Limits
    users = load_users()
    user_data = users[st.session_state.user_email]
    
    if user_data['tier'] == 'free' and user_data['reports_generated'] >= user_data['max_free_reports']:
        st.error("🚫 **Free tier limit reached.** Please upgrade to Pro in the sidebar to generate more reports.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    full_prompt = prompt
    if st.session_state.document_context != "":
        full_prompt = f"CONFIDENTIAL DOCUMENT PROVIDED BY CLIENT:\n\n{st.session_state.document_context}\n\nCLIENT'S DIRECTIVE REGARDING DOCUMENT: {prompt}"

    with st.chat_message("assistant"):
        with st.spinner("Swarm is conducting deep research..."):
            try:
                result = run_swarm(full_prompt)
                # Increment report count on successful generation
                users[st.session_state.user_email]['reports_generated'] += 1
                save_users(users)
            except Exception as e:
                result = {"plan": [], "final_answer": f"⚠️ Swarm Critical Error: `{e}`"}
        
        clean_route = list(dict.fromkeys(result.get("plan", [])))
        if clean_route:
            route_text = " ➔ ".join(clean_route)
            st.markdown(f'<div class="route-pill"><span class="route-dot"></span>{route_text}</div>', unsafe_allow_html=True)

        final_output = result.get("final_answer", "Swarm failed to generate a response.")
        
        display_output = final_output
        if "EXECUTIVE BOTTOM LINE:" in display_output:
            display_output = display_output.replace("🎯 EXECUTIVE BOTTOM LINE:", "<div class='exec-section'><div class='exec-label'>🎯 Executive Bottom Line</div>")
            display_output = display_output.replace("🧠 STRATEGIC CONTEXT:", "</div><div class='exec-section'><div class='exec-label'>🧠 Strategic Context</div>")
            display_output = display_output.replace("🚨 RISK FACTORS:", "</div><div class='exec-section'><div class='exec-label'>🚨 Risk Factors</div>")
            display_output = display_output.replace("📊 KEY DATA POINTS:", "</div><div class='exec-section'><div class='exec-label'>📊 Key Data Points</div>")
            display_output += "</div>"
            st.markdown(display_output, unsafe_allow_html=True)
        else:
            st.markdown(display_output)

    st.session_state.messages.append({"role": "assistant", "content": final_output, "route": clean_route})
