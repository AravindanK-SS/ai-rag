"""
MCP Dynamic Tool Agent (host).
Discovers tools (and resources) at runtime from the servers listed in a config file.
Contains ZERO hardcoded tool names: adding or removing a server is a config-only change.

The model runs HERE, in the host. MCP servers only expose capabilities.
  - Primary path: Ollama native tool-calling over the discovered tools/list schemas.
  - Fallback path (Ollama down / model not pulled): a schema-driven planner that scores
    tools by overlap between the query and their own descriptions and fills arguments
    from their own JSON schemas. Still no tool names in this file.
"""
import os
import sys
import json
import re
from typing import Dict, Any, List, Optional
from src.mcp_client import MCPClient
from src.ollama_chat import OllamaChat, OllamaUnavailable

MAX_STEPS = 6
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
STOPWORDS = {"what", "the", "and", "for", "with", "that", "this", "from", "have", "does",
             "give", "tell", "about", "say", "using", "into", "your", "their", "get"}

SYSTEM_PROMPT = (
    "You are an HR policy assistant. Answer using the provided tools and context only. "
    "If a tool returns a 'Recoverable Error', follow the instructions in that message and call "
    "the tool again with corrected arguments. If a tool is denied, explain what is denied and "
    "what alternative is available. Never invent employee data or policy text."
)


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z]+", text.lower())
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w
            for w in words if len(w) >= 3 and w not in STOPWORDS}


class MCPAgent:
    def __init__(self, config_path: str = "config/mcp_servers.json", llm: Any = "auto"):
        self.config_path = config_path
        self.clients: Dict[str, MCPClient] = {}
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self.resources: List[Dict[str, Any]] = []
        if os.environ.get("MCP_AGENT_NO_LLM") == "1":
            llm = None
        self.llm = OllamaChat() if llm == "auto" else llm
        self.load_servers_from_config()

    # ---------------------------------------------------------------- discovery
    def load_servers_from_config(self):
        """Discovers tools/resources by connecting to every MCP server in the config."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"MCP configuration file not found at: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        for server_name, server_cfg in config.get("mcpServers", {}).items():
            command = server_cfg.get("command", sys.executable)
            if command == "python":
                command = sys.executable
            client = MCPClient(name=server_name, command=command,
                               args=server_cfg.get("args", []), env=server_cfg.get("env"))
            client.start()
            self.clients[server_name] = client

            for tool_meta in client.list_tools():
                self.tools_registry[tool_meta["name"]] = {
                    "server_name": server_name, "client": client, "schema": tool_meta}

            # Resources are app-attached context, not model-invoked tools.
            for res in client.list_resources():
                self.resources.append({"server_name": server_name, "client": client, **res})

    def get_discovered_tools(self) -> List[Dict[str, Any]]:
        return [meta["schema"] for meta in self.tools_registry.values()]

    def list_discovered_tool_names(self) -> List[str]:
        return list(self.tools_registry.keys())

    def _attached_context(self) -> str:
        parts = []
        for res in self.resources:
            try:
                parts.append(f"[{res.get('name', res['uri'])}]\n{res['client'].read_resource(res['uri'])}")
            except Exception as e:
                parts.append(f"[{res.get('name', res['uri'])}] unavailable: {e}")
        return "\n\n".join(parts)

    # ---------------------------------------------------------------- tool execution
    def _execute(self, name: str, args: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
        entry = self.tools_registry.get(name)
        step = {"tool": name, "server": entry["server_name"] if entry else None,
                "arguments": args, "result": None, "is_error": False}
        if not entry:
            step.update(result=f"Unknown tool '{name}'. Available: {self.list_discovered_tool_names()}",
                        is_error=True)
        else:
            print(f"[Agent] Action -> Calling Tool: '{name}' with args: {args} on server: '{entry['server_name']}'")
            try:
                res = entry["client"].call_tool(name, args)
                step["result"] = "\n".join(c.get("text", "") for c in res.get("content", [])
                                           if c.get("type") == "text")
                step["is_error"] = res.get("isError", False)
            except Exception as e:
                step.update(result=str(e), is_error=True)
            print(f"[Agent] Observation: {step['result']}")
        trace["steps"].append(step)
        return step

    # ---------------------------------------------------------------- LLM path
    def _run_llm(self, query: str, trace: Dict[str, Any]) -> bool:
        tools = [{"type": "function", "function": {
                    "name": t["name"], "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}})}}
                 for t in self.get_discovered_tools()]
        system = SYSTEM_PROMPT
        context = self._attached_context()
        if context:
            system += "\n\nReference context:\n" + context
        messages = [{"role": "system", "content": system}, {"role": "user", "content": query}]

        for _ in range(MAX_STEPS):
            msg = self.llm.chat(messages, tools)  # raises OllamaUnavailable on first failure
            calls = msg.get("tool_calls") or []
            if not calls:
                trace["final_answer"] = (msg.get("content") or "").strip() or self._join_observations(trace)
                return True
            messages.append(msg)
            for call in calls:
                fn = call.get("function", {})
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args or "{}")
                step = self._execute(fn.get("name", ""), args, trace)
                messages.append({"role": "tool", "tool_name": fn.get("name", ""), "content": step["result"]})
        trace["final_answer"] = self._join_observations(trace) or "Stopped: step limit reached."
        return True

    # ---------------------------------------------------------------- fallback path
    def _plan_from_schemas(self, query: str) -> List[Dict[str, Any]]:
        q_tokens = _tokens(query)
        scored = []
        for name, entry in self.tools_registry.items():
            schema = entry["schema"]
            props = schema.get("inputSchema", {}).get("properties", {})
            t_tokens = _tokens(name.replace("_", " ") + " " + schema.get("description", "")
                               + " " + " ".join(props))
            scored.append((len(q_tokens & t_tokens), name))
        if not scored:
            return []
        best = max(s for s, _ in scored)
        return [{"name": n, "arguments": self._fill_arguments(self.tools_registry[n]["schema"], query)}
                for s, n in scored if s >= 2 and s >= 0.5 * best]

    @staticmethod
    def _fill_arguments(schema: Dict[str, Any], query: str) -> Dict[str, Any]:
        input_schema = schema.get("inputSchema", {})
        required = set(input_schema.get("required", []))
        args: Dict[str, Any] = {}
        for prop, spec in input_schema.get("properties", {}).items():
            desc = spec.get("description", "")
            value = None
            if spec.get("enum"):
                value = next((e for e in spec["enum"] if str(e).lower() in query.lower()), None)
            elif "YYYY-MM-DD" in desc:
                m = DATE_RE.search(query)
                value = m.group(1) if m else spec.get("default")
            else:
                # Identifier shape derived from the example in the property's own description.
                ex = re.search(r"'([A-Za-z]+\d+)'", desc)
                if ex:
                    shape = "".join(r"[A-Za-z]" if c.isalpha() else r"\d" for c in ex.group(1))
                    m = re.search(rf"\b{shape}\b", query)
                    value = m.group(0).upper() if m else None
                elif spec.get("type") == "string":
                    value = query
            if value is not None:
                args[prop] = value
            elif prop in required:
                args[prop] = ""
        return args

    def _run_fallback(self, query: str, trace: Dict[str, Any]):
        calls = self._plan_from_schemas(query)
        if not calls:
            trace["final_answer"] = f"No applicable tool found among discovered tools for query: '{query}'"
            return
        for call in calls:
            step = self._execute(call["name"], call["arguments"], trace)
            if step["is_error"]:
                # One recovery attempt: reuse a corrected date quoted in the error message.
                old = next((v for v in call["arguments"].values()
                            if isinstance(v, str) and DATE_RE.fullmatch(v)), None)
                fixed = next((d for d in DATE_RE.findall(step["result"] or "") if d != old), None)
                if fixed and old:
                    retry = {k: (fixed if v == old else v) for k, v in call["arguments"].items()}
                    self._execute(call["name"], retry, trace)
        trace["final_answer"] = self._join_observations(trace)

    @staticmethod
    def _join_observations(trace: Dict[str, Any]) -> str:
        return " ".join(s["result"] for s in trace["steps"] if s["result"])

    # ---------------------------------------------------------------- public API
    def run(self, query: str) -> Dict[str, Any]:
        """Runs the agent with an execution trace, logging every step."""
        trace = {"query": query, "discovered_tools": self.list_discovered_tool_names(),
                 "mode": "llm", "steps": [], "final_answer": ""}
        print(f"\n[Agent] Received Query: {query}")
        print(f"[Agent] Active Discovered Tools ({len(self.tools_registry)}): {self.list_discovered_tool_names()}")

        if self.llm is not None:
            try:
                self._run_llm(query, trace)
                print(f"[Agent] Final Answer: {trace['final_answer']}\n")
                return trace
            except OllamaUnavailable as e:
                trace["mode"] = f"fallback (LLM unavailable: {e})"
                trace["steps"].clear()
        else:
            trace["mode"] = "fallback (LLM disabled)"
        print(f"[Agent] Mode: {trace['mode']}")
        self._run_fallback(query, trace)
        print(f"[Agent] Final Answer: {trace['final_answer']}\n")
        return trace

    def shutdown(self):
        for client in self.clients.values():
            client.stop()


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/mcp_servers.json"
    agent = MCPAgent(config_path=cfg)
    agent.run(sys.argv[2] if len(sys.argv) > 2 else
              "What is the grade band and accrued leave balance for EMP001?")
    agent.shutdown()
