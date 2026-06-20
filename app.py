import streamlit as st
import sys
import os
import PyPDF2

sys.path.append(os.path.dirname(__file__))
from swarm_engine import run_swarm

# ─────────────────────────────────────────────────────────────────────────────
# 1. AGENCY CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
AGENCY_NAME = "DealScout Intelligence™"
ACCESS_CODE = os.environ.get("AGENCY_ACCESS_CODE", "sovereign") # Default for local dev

st.set_page_config(page_title=AGENCY_NAME, layout="centered", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────────────────────────────────────
# 2. PREMIUM UI STYLING (Dark Mode, Executive Aesthetic)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
html, body, [data-testid="stAppViewContainer"] { background: #09090b !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stMain"] > div { max-width: 800px !important; margin: 0 auto !important; padding: 0 24px !important; }

/* Header & Typography */
.agency-header { text-align: center; padding: 48px 0 32px; border-bottom: 1px solid #27272a; margin-bottom: 32px; }
.agency-logo { font-size: 40px; margin-bottom: 8px; }
.agency-title { font-size: 22px; font-weight: 600; color: #fafafa; letter-spacing: -0.5px; margin: 0; }
.agency-sub { font-size: 13px; color: #71717a; margin-top: 6px; text-transform: uppercase; letter-spacing: 1px; }

/* Chat Messages */
[data-testid="stChatMessage"] { background: transparent !important; border: none !important; padding: 0 !important; margin-bottom: 32px !important; gap: 12px !important; }
[data-testid="chatAvatarIcon-user"] { background: #27272a !important; color: #a1a1aa !important; width: 28px !important; height: 28px !important; border-radius: 4px !important; }
[data-testid="chatAvatarIcon-assistant"] { background: #f59e0b !important; color: #000 !important; width: 28px !important; height: 28px !important; border-radius: 4px !important; }
[data-testid="stMarkdownContainer"] p { font-size: 15px !important; line-height: 1.8 !important; color: #d4d4d8 !important; margin: 0 0 8px !important; }
[data-testid="stMarkdownContainer"] strong { color: #fafafa !important; font-weight: 600 !important; }

/* Route Pills (Agent History) */
.route-pill { display: inline-flex; align-items: center; gap: 6px; background: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 4px 12px; font-size: 11px; color: #71717a; margin-bottom: 16px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
.route-dot { width: 6px; height: 6px; border-radius: 50%; background: #f59e0b; display: inline-block; }

/* Executive Report Formatting */
.exec-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid #27272a; }
.exec-label { font-size: 12px; font-weight: 600; color: #f59e0b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }

/* Input & Buttons */
[data-testid="stChatInput"] { background: #18181b !important; border: 1px solid #27272a !important; border-radius: 8px !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; color: #e4e4e7 !important; font-size: 15px !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #3f3f46 !important; }
.stButton>button { background: #f59e0b !important; color: #000 !important; border: none !important; font-weight: 600 !important; border-radius: 6px !important; }
.stButton>button:hover { background: #d97706 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 3. SECURITY GATE (Agency Model)
# ─────────────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown(f"""
    <div class="agency-header">
        <div class="agency-logo">📊</div>
        <p class="agency-title">{AGENCY_NAME}</p>
        <p class="agency-sub">Autonomous B2B Intelligence & Risk Mitigation</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='max-width: 400px; margin: 40px auto; text-align: center;'></div>", unsafe_allow_html=True)
    access_input = st.text_input("Enter Access Code to Unlock Swarm:", type="password", key="gate")
    
    if st.button("Unlock Platform"):
        if access_input == ACCESS_CODE:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("⚠️ Invalid Access Code. This platform is for authorized personnel only.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# 4. SECURE DEAL ROOM (PDF Vault)
# ─────────────────────────────────────────────────────────────────────────────
if "document_context" not in st.session_state:
    st.session_state.document_context = ""

with st.sidebar:
    st.markdown("<h3 style='color: #fafafa; font-weight: 600;'>📂 Secure Deal Room</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #71717a; font-size: 13px;'>Upload Pitch Decks, 10-Ks, or Market Reports. Processed locally.</p>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("", type="pdf")
    
    if uploaded_file is not None:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text()])
            if len(text) > 12000: text = text[:12000] + "\n\n...[Document Truncated for Swarm Memory]..."
            st.session_state.document_context = text
            st.success("✅ Securely Loaded into Memory")
            with st.expander("Preview Extracted Text"):
                st.write(text[:300] + "...")
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            
    st.divider()
    if st.button("🔒 Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN DASHBOARD
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

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("route"):
            route_text = " ➔ ".join(msg["route"])
            st.markdown(f'<div class="route-pill"><span class="route-dot"></span>{route_text}</div>', unsafe_allow_html=True)
        
        # Beautiful formatting for the final executive report
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
# 6. CHAT INPUT & SWARM EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Initiate intelligence gathering..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build the full prompt with PDF context
    full_prompt = prompt
    if st.session_state.document_context != "":
        full_prompt = f"CONFIDENTIAL DOCUMENT PROVIDED BY CLIENT:\n\n{st.session_state.document_context}\n\nCLIENT'S DIRECTIVE REGARDING DOCUMENT: {prompt}"

    with st.chat_message("assistant"):
        with st.spinner("Swarm is conducting deep research..."):
            try:
                result = run_swarm(full_prompt)
            except Exception as e:
                result = {"plan": [], "final_answer": f"⚠️ Swarm Critical Error: `{e}`"}
        
        # Clean up route duplicates
        clean_route = list(dict.fromkeys(result.get("plan", [])))
        if clean_route:
            route_text = " ➔ ".join(clean_route)
            st.markdown(f'<div class="route-pill"><span class="route-dot"></span>{route_text}</div>', unsafe_allow_html=True)

        final_output = result.get("final_answer", "Swarm failed to generate a response.")
        
        # Display beautifully
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
