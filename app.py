"""
app.py — DealScout Swarm, Streamlit Cloud entry point.

This is the file you point Streamlit Cloud at (App settings -> Main file path: app.py).
It has two tabs:
  1. Run Engagement  -- the actual product: type a request, run the swarm, see the report
     and the full agent trace.
  2. Diagnostics      -- a live, in-app version of verify_search_setup.py. Streamlit Cloud
     gives you no terminal access once deployed, so this is how you check which search
     providers and which keys are actually working *in the deployed app*, not just locally.
"""
import os
import time

import streamlit as st
import httpx

import dealscout_engine as engine

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

st.set_page_config(page_title="DealScout Swarm", page_icon="🦉", layout="wide")

# ------------------------------------------------------------------------------------
# Diagnostics checks (same logic as verify_search_setup.py, reused here so you can run
# them against the ACTUAL deployed environment's secrets, not just your local machine).
# ------------------------------------------------------------------------------------
TEST_QUERY = "Zerodha vs Groww market share India"


def check_groq():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return "MISSING", "Set GROQ_API_KEY in App settings -> Secrets (required -- nothing runs without it)."
    try:
        resp = engine.get_client().chat.completions.create(
            model=engine.MODEL,
            messages=[{"role": "user", "content": "Reply with just the word OK."}],
            max_tokens=5,
        )
        return "OK", f"Groq reachable, model responded: {resp.choices[0].message.content!r}"
    except Exception as e:
        return "FAIL", str(e)


def check_serper():
    key = os.environ.get("SERPER_API_KEY")
    if not key:
        return "SKIPPED", "SERPER_API_KEY not set (optional -- ddgs is the free fallback)."
    try:
        r = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": TEST_QUERY, "gl": engine.SEARCH_REGION, "hl": "en", "num": 3},
            timeout=10,
        )
        r.raise_for_status()
        organic = r.json().get("organic", [])
        if not organic:
            return "FAIL", "200 OK but no organic results returned."
        return "OK", f"{len(organic)} results, first: {organic[0].get('title', '')!r}"
    except Exception as e:
        return "FAIL", str(e)


def check_brave():
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return "SKIPPED", "BRAVE_API_KEY not set (optional)."
    try:
        r = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            params={"q": TEST_QUERY, "country": engine.SEARCH_REGION, "count": 3},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])
        if not results:
            return "FAIL", "200 OK but no web results returned."
        return "OK", f"{len(results)} results, first: {results[0].get('title', '')!r}"
    except Exception as e:
        return "FAIL", str(e)


def check_google_cse():
    key, cx = os.environ.get("GOOGLE_CSE_API_KEY"), os.environ.get("GOOGLE_CSE_CX")
    if not (key and cx):
        return "SKIPPED", "GOOGLE_CSE_API_KEY / GOOGLE_CSE_CX not set (optional)."
    try:
        r = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": key, "cx": cx, "q": TEST_QUERY, "gl": engine.SEARCH_REGION, "num": 3},
            timeout=10,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return "FAIL", "200 OK but no items returned."
        return "OK", f"{len(items)} results, first: {items[0].get('title', '')!r}"
    except Exception as e:
        return "FAIL", str(e)


def check_ddgs():
    if DDGS is None:
        return "FAIL", "Neither 'ddgs' nor 'duckduckgo_search' is installed (check requirements.txt)."
    try:
        with DDGS(timeout=10) as ddgs:
            results = list(ddgs.text(TEST_QUERY, region=f"{engine.SEARCH_REGION}-en", safesearch="off", max_results=3))
        if not results:
            return "FAIL", "No results (often a rate-limit/anti-bot block from DDG, not a real empty answer)."
        return "OK", f"{len(results)} results, first: {results[0].get('title', '')!r}"
    except Exception as e:
        return "FAIL", str(e)


def check_registry():
    if engine.INDIA_REGISTRY_PROVIDER == "none" or not engine.INDIA_REGISTRY_API_KEY:
        return "SKIPPED", "Not configured -- scaffolding only, see code comments to wire up Tofler/Probe42."
    return "INFO", f"Provider set to '{engine.INDIA_REGISTRY_PROVIDER}', but the request is not yet implemented (see code)."


# ------------------------------------------------------------------------------------
# UI
# ------------------------------------------------------------------------------------
st.title("🦉 DealScout Swarm — India Edition")

tab_run, tab_diag = st.tabs(["▶️ Run Engagement", "🔧 Diagnostics"])

with tab_run:
    st.caption(
        "Five AI agents — Engagement Manager, Market Intelligence Analyst, Strategy Associate, "
        "Risk Director, Managing Partner — research, draft, stress-test, and deliver a sourced memo."
    )
    request_text = st.text_area(
        "Client request",
        placeholder="e.g. Should a seed-stage fintech in Bangalore compete with Razorpay on payment gateway fees, or focus on a niche?",
        height=100,
    )
    run_clicked = st.button("Run Engagement", type="primary", disabled=not request_text.strip())

    if run_clicked:
        if not os.environ.get("GROQ_API_KEY"):
            st.error(
                "GROQ_API_KEY is not set. Go to App settings → Secrets, add it as a root-level "
                "key, then reboot the app. Check the Diagnostics tab for the full picture."
            )
        else:
            with st.spinner("Swarm running — this can take 30–90 seconds across 5 agents..."):
                try:
                    result = engine.run_swarm(request_text.strip())
                except Exception as e:
                    st.error(f"Swarm crashed: {e}")
                    result = None

            if result:
                st.subheader("📋 Final Report")
                st.markdown(result["final_answer"])

                with st.expander(f"🔍 Agent trace ({len(result['plan'])} steps) — see exactly what each agent did and why"):
                    st.write("**Agent sequence:**", " → ".join(result["plan"]))
                    for msg in result["history"]:
                        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "?")
                        if role == "tool":
                            name = msg.get("name") if isinstance(msg, dict) else getattr(msg, "name", "?")
                            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                            st.text(f"[{name}] {content}")
                        elif role == "user":
                            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                            st.text(f"[handoff/user] {content}")

with tab_diag:
    st.caption(
        "Runs the same checks as verify_search_setup.py, but against THIS deployed app's "
        "actual secrets — Streamlit Cloud gives no terminal access, so this is how you "
        "confirm what's really working after you deploy, not just on your laptop."
    )
    if st.button("Run diagnostics"):
        checks = [
            ("Groq (required)", check_groq),
            ("Serper", check_serper),
            ("Brave", check_brave),
            ("Google CSE", check_google_cse),
            ("DDGS (free fallback)", check_ddgs),
            ("India registry lookup", check_registry),
        ]
        for label, fn in checks:
            status, detail = fn()
            if status == "OK":
                st.success(f"**{label}**: {detail}")
            elif status == "SKIPPED":
                st.info(f"**{label}**: {detail}")
            elif status == "MISSING":
                st.error(f"**{label}**: {detail}")
            else:
                st.warning(f"**{label}**: {detail}")
            time.sleep(0.2)
