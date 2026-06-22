import os
import json
import re
from typing import List, Dict
from openai import OpenAI # Using OpenAI SDK for both Groq and NVIDIA NIM

# FIX: Handle the DDGS package rename gracefully
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

print("[*] Initializing DealScout Swarm™ (v19.0 - Sovereign Pro Stack)...")

# ==============================================================================
# 1. DYNAMIC AI BRAIN ROUTER (Verified Sovereign Models)
# ==============================================================================
AGENT_MODELS = {
    # NOTE (June 2026): llama3-8b-8192 was decommissioned by Groq on 08/30/2025.
    # llama-3.3-70b-versatile was deprecated 06/17/2026, shutdown 08/16/2026 —
    # migrating straight to the GPT-OSS models now avoids a second fire drill in August.
    # See https://console.groq.com/docs/deprecations
    # Pro-tier strings below are NVIDIA NIM catalog IDs (build.nvidia.com), not OpenRouter.
    "Engagement_Manager": {
        "free": "groq/openai/gpt-oss-20b",
        "pro": "mistralai/mistral-small-4-119b-2603"  # Extremely fast, high IQ, perfect for routing
    },
    "Market_Intelligence_Analyst": {
        "free": "groq/openai/gpt-oss-120b",
        "pro": "qwen/qwen3-next-80b-a3b-instruct"     # THE KING of web data parsing & extraction
    },
    "Strategy_Associate": {
        "free": "groq/openai/gpt-oss-120b",
        "pro": "meta/llama-3.1-70b-instruct"          # Heavy hitter for writing executive strategy
    },
    "Risk_Director": {
        "free": "groq/openai/gpt-oss-120b",
        "pro": "meta/llama-3.1-70b-instruct"          # Heavy hitter for deep logic & catching flaws
    },
    "Managing_Partner": {
        "free": "groq/openai/gpt-oss-20b",
        "pro": "mistralai/mistral-small-4-119b-2603"  # Lightning fast, flawless formatting
    }
}

def get_client_for_model(tier: str, agent_name: str):
    """Routes to the correct API provider based on user tier and agent role."""
    model_name = AGENT_MODELS.get(agent_name, {}).get(tier, "groq/openai/gpt-oss-120b")
    
    if "groq" in model_name:
        # FREE TIER -> Use Groq (Cost: $0.00)
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY"), 
            base_url="https://api.groq.com/openai/v1"
        )
        # Strip the "groq/" prefix for Groq's API
        actual_model_name = model_name.replace("groq/", "")
        return client, actual_model_name
    else:
        # PRO TIER -> Use NVIDIA NIM (build.nvidia.com free API; Qwen, Mistral, Llama)
        client = OpenAI(
            api_key=os.environ.get("NVIDIA_API_KEY"),
            base_url="https://integrate.api.nvidia.com/v1"
        )
        return client, model_name

# ==============================================================================
# 2. SHARED WORKSPACE
# ==============================================================================
class SwarmState:
    def __init__(self, query: str):
        self.query = query
        self.plan = []
        self.artifacts = {}
        self.messages = []
        self.current_agent = None

    def add_artifact(self, key: str, value: str):
        self.artifacts[key] = value

    def get_artifact(self, key: str) -> str:
        return self.artifacts.get(key, "No data available.")

    def to_dict(self):
        return {
            "plan": self.plan,
            "final_answer": self.artifacts.get("final_answer", "Error: No final answer generated."),
            "history": self.messages
        }

# ==============================================================================
# 3. AGENT DEFINITIONS (B2B CONSULTING PERSONAS)
# ==============================================================================
AGENT_DEFS = {
    "Engagement_Manager": {
        "system_prompt": "You are the Engagement Manager at a top-tier consulting firm. Analyze the client's request. If they need market research, competitor analysis, or deal evaluation, delegate to Market_Intelligence_Analyst. Otherwise, delegate to Strategy_Associate. Be professional and concise.",
        "tools": ["delegate_to_agent"],
        "allowed_transitions": ["Market_Intelligence_Analyst", "Strategy_Associate"]
    },
    "Market_Intelligence_Analyst": {
        "system_prompt": (
            "You are a Senior Market Intelligence Analyst. Your job is to gather raw, actionable intelligence and hand off to the Strategy_Associate.\n"
            "WORKFLOW:\n"
            "1. Call `tool_web_search` to find competitor data, market sizing, or recent news.\n"
            "2. CRITICAL: Extract specific company names, financial figures, and market shares. DO NOT output generic fluff like 'the market is growing'. Find the exact data points.\n"
            "3. If search FAILS, save an artifact stating: 'LIVE SEARCH FAILED. Strategy_Associate must rely on provided documents or inform client that live data is unavailable.'\n"
            "4. Save detailed findings using `save_artifact` with key 'market_intel'.\n"
            "5. Delegate to 'Strategy_Associate'.\n"
            "NEVER delegate to yourself."
        ),
        "tools": ["tool_web_search", "save_artifact", "delegate_to_agent"],
        "allowed_transitions": ["Strategy_Associate"]
    },
    "Strategy_Associate": {
        "system_prompt": (
            "You are a Strategy Associate. You write high-value executive memos.\n"
            "WORKFLOW:\n"
            "1. Read 'market_intel' from workspace using `read_artifact`.\n"
            "2. Write a comprehensive strategy draft. Tone: Objective, analytical, direct. No fluff.\n"
            "3. REQUIRED FORMAT (No exceptions):\n\n"
            "🎯 EXECUTIVE BOTTOM LINE:\n(2-3 sentences stating the exact strategic outcome or risk)\n\n"
            "🧠 STRATEGIC CONTEXT:\n(3-4 sentences on market positioning, implications, or competitive landscape)\n\n"
            "🚨 RISK FACTORS:\n- (Specific risk 1)\n- (Specific risk 2)\n\n"
            "📊 KEY DATA POINTS:\n- (Specific metric/fact 1)\n- (Specific metric/fact 2)\n\n"
            "4. Save draft using `save_artifact` with key 'strategy_draft'.\n"
            "5. Delegate to 'Risk_Director'.\n"
            "NEVER delegate to yourself."
        ),
        "tools": ["read_artifact", "save_artifact", "delegate_to_agent"],
        "allowed_transitions": ["Risk_Director"]
    },
    "Risk_Director": {
        "system_prompt": (
            "You are the Risk Director. You are the bad cop. Your job is to stress-test the Strategy_Associate's draft.\n"
            "WORKFLOW:\n"
            "1. Read 'strategy_draft' from workspace using `read_artifact`.\n"
            "CHECKS:\n"
            "- Is it too generic? (e.g., 'AI is growing'). If yes, REJECT and delegate back to Strategy_Associate with note: 'Too generic. Require specific competitor names and financial metrics.'\n"
            "- Are there missing risks? If yes, REJECT and delegate back to Strategy_Associate.\n"
            "- Did it follow the exact format? If no, REJECT.\n"
            "If it is sharp, accurate, and executive-ready, delegate to Managing_Partner. DO NOT delegate to yourself."
        ),
        "tools": ["read_artifact", "save_artifact", "delegate_to_agent"],
        "allowed_transitions": ["Strategy_Associate", "Managing_Partner"]
    },
    "Managing_Partner": {
        "system_prompt": (
            "You are the Managing Partner. Read the 'strategy_draft' using `read_artifact`.\n"
            "Convert it into a polished executive report and output it as a SINGLE valid JSON object "
            "(no markdown code fences, no commentary before or after) with EXACTLY this shape:\n"
            "{\n"
            '  "title": "<short report title>",\n'
            '  "executive_summary": "<2-3 sentence bottom line, plain text>",\n'
            '  "market_data": [{"label": "<metric name>", "value": "<metric value>", "trend": "<e.g. +12% or -3%, or empty string>"}],\n'
            '  "risk_matrix": [{"risk": "<risk description>", "severity": "High" or "Medium" or "Low"}]\n'
            "}\n"
            "Pull the metrics and risks directly from the strategy_draft — do not invent data that isn't there. "
            "Save ONLY that JSON string as 'final_answer' using `save_artifact`. Then use the `finish_task` tool to end the engagement. "
            "DO NOT change the core strategic insights, just restructure them into the JSON shape above."
        ),
        "tools": ["read_artifact", "save_artifact", "finish_task"],
        "allowed_transitions": []
    }
}

# ==============================================================================
# 4. TOOL IMPLEMENTATIONS
# ==============================================================================
def tool_web_search(query: str) -> str:
    clean_query = query.replace("top 3", "").replace("latest", "").strip()
    if not clean_query:
        clean_query = "market analysis"
    print(f"    [TOOL_EXEC] Searching: {clean_query!r}")
    try:
        with DDGS(timeout=10) as ddgs:
            results = list(ddgs.text(clean_query, region="wt-wt", safesearch="off", max_results=5))
        if not results:
            return "LIVE SEARCH FAILED: No results found."
        return "\n".join(f"[{i+1}] {r.get('title', '')}: {r.get('body', '')}" for i, r in enumerate(results))
    except Exception as e:
        return f"LIVE SEARCH FAILED: Search engine error ({e})."

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "delegate_to_agent", "description": "Hand off the current task to another agent.", "parameters": {"type": "object", "properties": {"agent_name": {"type": "string", "enum": list(AGENT_DEFS.keys())}, "message": {"type": "string"}}, "required": ["agent_name", "message"]}}},
    {"type": "function", "function": {"name": "tool_web_search", "description": "Search the web for market data, competitor info, or news.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "save_artifact", "description": "Save work to the shared workspace.", "parameters": {"type": "object", "properties": {"key": {"type": "string", "enum": ["market_intel", "strategy_draft", "final_answer"]}, "content": {"type": "string"}}, "required": ["key", "content"]}}},
    {"type": "function", "function": {"name": "read_artifact", "description": "Read an artifact from the workspace.", "parameters": {"type": "object", "properties": {"key": {"type": "string", "enum": ["market_intel", "strategy_draft"]}}, "required": ["key"]}}},
    {"type": "function", "function": {"name": "finish_task", "description": "End the swarm process.", "parameters": {"type": "object", "properties": {}}}}
]

def get_tool_schemas_for_agent(agent_name: str) -> list:
    allowed = set(AGENT_DEFS[agent_name]["tools"])
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in allowed]

def dispatch_tool_call(state: SwarmState, agent_name: str, agent_def: dict, func_name: str, func_args: dict):
    """Returns (observation: str, finished: bool)."""
    if func_name not in agent_def["tools"]:
        return (f"ERROR: {agent_name} is not permitted to use '{func_name}'. "
                f"Permitted tools: {agent_def['tools']}."), False

    if func_name == "delegate_to_agent":
        next_agent = func_args["agent_name"]
        if next_agent == agent_name:
            return (f"CRITICAL ERROR: You cannot delegate to yourself! You are {agent_name}. "
                     f"Delegate to: {agent_def['allowed_transitions']}."), False
        if next_agent not in agent_def["allowed_transitions"]:
            return (f"ERROR: You cannot delegate to {next_agent}. "
                     f"Delegate to: {agent_def['allowed_transitions']}."), False
        state.current_agent = next_agent
        handoff_note = func_args.get("message", "")
        # FIX: Fold handoff note into observation to prevent message-ordering 400 errors
        return f"Control handed over to {next_agent}. Handoff note from {agent_name}: {handoff_note}", False

    elif func_name == "save_artifact":
        state.add_artifact(func_args["key"], func_args["content"])
        return f"Artifact '{func_args['key']}' saved successfully.", False

    elif func_name == "read_artifact":
        return state.get_artifact(func_args["key"]), False

    elif func_name == "tool_web_search":
        return tool_web_search(**func_args), False

    elif func_name == "finish_task":
        if "final_answer" not in state.artifacts:
            state.add_artifact("final_answer", "Task finished, but no final answer was saved.")
        return "Task finished.", True

    return f"Error: Tool {func_name} not found.", False

# ==============================================================================
# 5. THE AGENTIC EXECUTION LOOP (Self-Healing + Dynamic Model Loading)
# ==============================================================================
def execute_agent_loop(state: SwarmState, tier: str = "free", max_steps: int = 30) -> dict:
    step = 0
    while step < max_steps:
        step += 1
        agent_name = state.current_agent
        agent_def = AGENT_DEFS[agent_name]
        
        # DYNAMIC MODEL LOADING: Get the right AI brain for this specific agent and tier
        client, model_name = get_client_for_model(tier, agent_name)
        print(f"\n[STEP {step}] Executing Agent: {agent_name} | Model: {model_name} | Tier: {tier}")
        
        state.plan.append(agent_name)
        api_messages = [{"role": "system", "content": agent_def["system_prompt"]}] + state.messages
        agent_tools = get_tool_schemas_for_agent(agent_name)

        try:
            response = client.chat.completions.create(
                model=model_name, messages=api_messages, tools=agent_tools,
                tool_choice="auto", max_tokens=2000, temperature=0.3,
                parallel_tool_calls=False
            )
        except Exception as e:
            error_str = str(e)
            # Self-Heal: Catch malformed XML function calls
            if "failed_generation" in error_str and "<function=" in error_str:
                print("    [SELF-HEAL] Caught malformed function call. Parsing manually...")
                match = re.search(r'<function=(\w+)>(\{.*?\})</function>', error_str)
                if match:
                    func_name, raw_args = match.group(1), match.group(2)
                    try:
                        func_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        state.add_artifact("final_answer", f"⚠️ Swarm API Error (unparseable self-heal args): {e}")
                        return state.to_dict()
                    print(f"    [SELF-HEAL] Manually executing: {func_name}({func_args})")
                    observation, finished = dispatch_tool_call(state, agent_name, agent_def, func_name, func_args)
                    healed_id = "healed_call_1"
                    state.messages.append({
                        "role": "assistant", "content": None,
                        "tool_calls": [{"id": healed_id, "type": "function",
                                        "function": {"name": func_name, "arguments": json.dumps(func_args)}}]
                    })
                    state.messages.append({"role": "tool", "name": func_name, "content": str(observation), "tool_call_id": healed_id})
                    if finished:
                        return state.to_dict()
                    continue
            
            # Catch Rate Limits
            elif "429" in error_str or "rate_limit" in error_str.lower():
                state.add_artifact("final_answer", "⚠️ **Swarm is at Capacity:** Servers experiencing high traffic. Please wait 60 seconds or upgrade to Pro for priority access.")
                return state.to_dict()
                
            state.add_artifact("final_answer", f"⚠️ Swarm API Error: {e}")
            return state.to_dict()

        choice = response.choices[0]
        if choice.finish_reason == "tool_calls":
            state.messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    # FIX: Feed JSON parse errors back to the model
                    state.messages.append({
                        "role": "tool", "name": tool_call.function.name,
                        "content": f"ERROR: Could not parse arguments as JSON: {tool_call.function.arguments!r}",
                        "tool_call_id": tool_call.id
                    })
                    continue

                func_name = tool_call.function.name
                print(f"    [ACTION] {func_name}({func_args})")
                observation, finished = dispatch_tool_call(state, agent_name, agent_def, func_name, func_args)

                state.messages.append({"role": "tool", "name": func_name, "content": str(observation), "tool_call_id": tool_call.id})

                if finished:
                    return state.to_dict()

        elif choice.finish_reason == "stop":
            state.messages.append({"role": "assistant", "content": choice.message.content})
            state.messages.append({"role": "user", "content": "You must use a tool to proceed. Delegate, save, or finish."})
        else:
            state.add_artifact("final_answer", f"⚠️ Swarm stopped unexpectedly (finish_reason='{choice.finish_reason}').")
            break

    if "final_answer" not in state.artifacts:
        state.add_artifact("final_answer", "⚠️ Swarm exceeded maximum steps without finishing.")
    return state.to_dict()

# ==============================================================================
# 6. ENTRY POINT
# ==============================================================================
def run_swarm(user_prompt: str, tier: str = "free") -> dict:
    print(f"\n[SWARM v19.0] Query: {user_prompt[:60]}... (Tier: {tier})")
    state = SwarmState(query=user_prompt)
    state.current_agent = "Engagement_Manager"
    state.messages.append({"role": "user", "content": f"Client Request: {user_prompt}\n\nPlease delegate this to the appropriate consultant."})
    return execute_agent_loop(state, tier=tier)
