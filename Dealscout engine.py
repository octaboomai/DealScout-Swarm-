import os
import json
import re
from typing import List, Dict
from groq import Groq

# duckduckgo_search was frozen by its maintainer in mid-2025 and renamed to `ddgs`.
# The old package still installs but no longer gets DuckDuckGo anti-bot fixes, so it
# silently degrades over time. Prefer `ddgs`; fall back to the legacy name only if
# that's all that's installed, so this doesn't hard-break on older environments.
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS  # legacy/frozen fallback only

print("[*] Initializing DealScout Swarm™ (v13.1 - Agency Edition, patched)...")

if not os.environ.get("GROQ_API_KEY"):
    raise RuntimeError("FATAL ERROR: GROQ_API_KEY environment variable is not set.")

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# ==============================================================================
# 1. SHARED WORKSPACE
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
# 2. AGENT DEFINITIONS (B2B CONSULTING PERSONAS)
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
        "system_prompt": "You are the Managing Partner. Read the 'strategy_draft' using `read_artifact`. Ensure it is perfectly formatted and polished. Save it as 'final_answer' using `save_artifact`. Then use the `finish_task` tool to end the engagement. DO NOT change the core strategic insights, just ensure executive readability.",
        "tools": ["read_artifact", "save_artifact", "finish_task"],
        "allowed_transitions": []
    }
}

# ==============================================================================
# 3. TOOL IMPLEMENTATIONS
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

# FIX (tool enforcement gap): every agent used to receive ALL 5 tool schemas regardless
# of agent_def["tools"]. This filters the schema sent to the model down to exactly what
# that agent is allowed to use, so e.g. Engagement_Manager can no longer be coaxed into
# calling tool_web_search and Managing_Partner can't call delegate_to_agent.
def get_tool_schemas_for_agent(agent_name: str) -> list:
    allowed = set(AGENT_DEFS[agent_name]["tools"])
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in allowed]


# FIX: tool dispatch is now a single shared function used by both the normal tool_calls
# path AND the self-heal path. This (a) fixes the self-heal branch, which previously
# could only "heal" tool_web_search and silently failed for every other tool, and
# (b) adds a server-side permission check so a tool call -- even a hand-parsed,
# self-healed one that bypassed the schema -- can't execute outside what that agent is
# allowed to do.
#
# FIX (message-ordering bug): delegate_to_agent used to insert a separate `role: user`
# handoff message into state.messages immediately after the assistant's tool_calls
# message but BEFORE the matching `role: tool` reply was appended. Groq/OpenAI-style
# APIs require every tool_call to be followed immediately by its own tool-role reply,
# with no other role interleaved -- so any turn with multiple tool calls (very common;
# e.g. tool_web_search + save_artifact + delegate_to_agent all in one turn) produced an
# invalid message sequence that would 400 on the *next* API call. The handoff note is
# now folded into the tool's own observation string instead of a separate message, so
# the sequence is always: assistant(tool_calls) -> tool, tool, tool... with nothing
# else in between.
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
# 4. THE AGENTIC EXECUTION LOOP (With Self-Healing)
# ==============================================================================
def execute_agent_loop(state: SwarmState, max_steps: int = 15) -> dict:
    step = 0
    while step < max_steps:
        step += 1
        agent_name = state.current_agent
        agent_def = AGENT_DEFS[agent_name]
        print(f"\n[STEP {step}] Executing Agent: {agent_name}")
        state.plan.append(agent_name)

        api_messages = [{"role": "system", "content": agent_def["system_prompt"]}] + state.messages
        agent_tools = get_tool_schemas_for_agent(agent_name)

        try:
            response = client.chat.completions.create(
                model=MODEL, messages=api_messages, tools=agent_tools,
                tool_choice="auto", max_tokens=2000, temperature=0.3
            )
        except Exception as e:
            error_str = str(e)
            # FIX: original regex was `<function=(\w+)=({.*?})</function>` which requires
            # an '=' directly before the JSON blob. The actual shape Groq returns in
            # failed_generation is `<function=NAME>{...}</function>` (a '>' , not '=').
            # The old pattern therefore could NEVER match, meaning self-heal was dead
            # code and the swarm just crashed the whole engagement on any malformed
            # function call. Confirmed with a regex test against a realistic error string.
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
            state.add_artifact("final_answer", f"⚠️ Swarm API Error: {e}")
            return state.to_dict()

        choice = response.choices[0]
        if choice.finish_reason == "tool_calls":
            state.messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    # FIX: malformed JSON arguments used to crash the whole process.
                    # Now we feed the error back to the model as a tool result so it
                    # can retry with valid arguments.
                    state.messages.append({
                        "role": "tool", "name": tool_call.function.name,
                        "content": f"ERROR: Could not parse arguments as JSON: {tool_call.function.arguments!r}",
                        "tool_call_id": tool_call.id
                    })
                    continue

                func_name = tool_call.function.name
                print(f"    [ACTION] {func_name}({func_args})")
                observation, finished = dispatch_tool_call(state, agent_name, agent_def, func_name, func_args)

                # Every tool_call gets exactly one tool-role reply, appended right away,
                # with nothing else interleaved -- this is what keeps the message
                # sequence valid for the next API call.
                state.messages.append({"role": "tool", "name": func_name, "content": str(observation), "tool_call_id": tool_call.id})

                if finished:
                    return state.to_dict()

        elif choice.finish_reason == "stop":
            state.messages.append({"role": "assistant", "content": choice.message.content})
            state.messages.append({"role": "user", "content": "You must use a tool to proceed. Delegate, save, or finish."})
        else:
            # FIX: previously this just `break`-ed and let the generic "exceeded maximum
            # steps" message overwrite the real reason. Now we record what actually
            # happened (e.g. finish_reason == "length" or "content_filter").
            state.add_artifact("final_answer", f"⚠️ Swarm stopped unexpectedly (finish_reason='{choice.finish_reason}').")
            break

    if "final_answer" not in state.artifacts:
        state.add_artifact("final_answer", "⚠️ Swarm exceeded maximum steps without finishing.")
    return state.to_dict()

# ==============================================================================
# 5. ENTRY POINT
# ==============================================================================
def run_swarm(user_prompt: str) -> dict:
    print(f"\n[SWARM v13.1] Query: {user_prompt[:60]}...")
    state = SwarmState(query=user_prompt)
    state.current_agent = "Engagement_Manager"
    state.messages.append({"role": "user", "content": f"Client Request: {user_prompt}\n\nPlease delegate this to the appropriate consultant."})
    return execute_agent_loop(state)
