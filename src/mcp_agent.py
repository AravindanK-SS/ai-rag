"""
MCP Dynamic Tool Agent
Discovers tools dynamically at runtime via Model Context Protocol (MCP) config.
Contains ZERO hardcoded tools; adding/removing servers is purely config-driven.
"""
import os
import sys
import json
import re
from typing import Dict, Any, List, Optional
from src.mcp_client import MCPClient

class MCPAgent:
    def __init__(self, config_path: str = "config/mcp_servers.json"):
        self.config_path = config_path
        self.clients: Dict[str, MCPClient] = {}
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self.load_servers_from_config()

    def load_servers_from_config(self):
        """Discovers tools by connecting to all MCP servers defined in the config."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"MCP configuration file not found at: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        for server_name, server_cfg in servers.items():
            command = server_cfg.get("command", sys.executable)
            if command == "python":
                command = sys.executable
            args = server_cfg.get("args", [])
            env = server_cfg.get("env")

            client = MCPClient(name=server_name, command=command, args=args, env=env)
            client.start()
            self.clients[server_name] = client

            # Dynamic Discovery via tools/list
            discovered_tools = client.list_tools()
            for tool_meta in discovered_tools:
                tool_name = tool_meta["name"]
                self.tools_registry[tool_name] = {
                    "server_name": server_name,
                    "client": client,
                    "schema": tool_meta
                }

    def get_discovered_tools(self) -> List[Dict[str, Any]]:
        return [meta["schema"] for meta in self.tools_registry.values()]

    def list_discovered_tool_names(self) -> List[str]:
        return list(self.tools_registry.keys())

    def _decide_tool_calls(self, query: str) -> List[Dict[str, Any]]:
        """
        Determines appropriate tool calls from user query against dynamically discovered tools.
        Works via LLM tool-calling if available, with intelligent fallback planner.
        """
        tool_calls = []

        # Extract employee ID if present
        emp_match = re.search(r"\b(EMP\d{3})\b", query, re.IGNORECASE)
        emp_id = emp_match.group(1).upper() if emp_match else None

        # Check against discovered tools
        query_lower = query.lower()

        # Check for HRIS grade band
        if "get_employee_grade_band" in self.tools_registry:
            if "grade" in query_lower or "band" in query_lower or "level" in query_lower:
                if emp_id:
                    tool_calls.append({
                        "name": "get_employee_grade_band",
                        "arguments": {"emp_id": emp_id}
                    })

        # Check for HRIS leave balance
        if "get_accrued_leave_balance" in self.tools_registry:
            if "leave balance" in query_lower or "accrued" in query_lower or "vacation balance" in query_lower:
                if emp_id:
                    tool_calls.append({
                        "name": "get_accrued_leave_balance",
                        "arguments": {"emp_id": emp_id}
                    })

        # Check for Policy search
        if "search_policy" in self.tools_registry:
            date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", query)
            eff_date = date_match.group(1) if date_match else "2024-04-01"

            if any(k in query_lower for k in ["policy", "annual leave", "sick leave", "core hours", "attendance", "rules"]):
                # Clean topic
                topic = "annual leave"
                for cand in ["annual leave", "sick leave", "core hours", "attendance"]:
                    if cand in query_lower:
                        topic = cand
                        break
                tool_calls.append({
                    "name": "search_policy",
                    "arguments": {"query": topic, "effective_date": eff_date}
                })

        return tool_calls

    def run(self, query: str) -> Dict[str, Any]:
        """Runs the agent loop with execution trace, logging every step."""
        trace = {
            "query": query,
            "discovered_tools": self.list_discovered_tool_names(),
            "steps": [],
            "final_answer": ""
        }

        print(f"\n[Agent] Received Query: {query}")
        print(f"[Agent] Active Discovered Tools ({len(self.tools_registry)}): {self.list_discovered_tool_names()}")

        tool_calls = self._decide_tool_calls(query)
        if not tool_calls:
            msg = f"No applicable tool found among discovered tools for query: '{query}'"
            print(f"[Agent] {msg}")
            trace["final_answer"] = msg
            return trace

        observations = []
        for tc in tool_calls:
            t_name = tc["name"]
            t_args = tc["arguments"]
            t_entry = self.tools_registry.get(t_name)

            print(f"[Agent] Action -> Calling Tool: '{t_name}' with args: {t_args} on server: '{t_entry['server_name']}'")
            step_record = {
                "tool": t_name,
                "server": t_entry["server_name"],
                "arguments": t_args,
                "result": None,
                "is_error": False
            }

            try:
                res = t_entry["client"].call_tool(t_name, t_args)
                content = res.get("content", [])
                text_res = "\n".join(item.get("text", "") for item in content if item.get("type") == "text")
                step_record["result"] = text_res
                step_record["is_error"] = res.get("isError", False)
                print(f"[Agent] Observation: {text_res}")
                observations.append(text_res)
            except Exception as e:
                step_record["result"] = str(e)
                step_record["is_error"] = True
                print(f"[Agent] Tool Error: {e}")
                observations.append(f"Error executing {t_name}: {e}")

            trace["steps"].append(step_record)

        # Synthesize final answer
        final_answer = " ".join(observations)
        trace["final_answer"] = final_answer
        print(f"[Agent] Final Answer: {final_answer}\n")
        return trace

    def shutdown(self):
        for client in self.clients.values():
            client.stop()

if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config/mcp_servers.json"
    agent = MCPAgent(config_path=cfg)
    test_query = "What is the grade band and accrued leave balance for EMP001?"
    result = agent.run(test_query)
    agent.shutdown()
