#!/usr/bin/env python3
"""
MCP Gateway Process (Bonus Challenge)
One front door for the agent: fans out to the downstream MCP servers, writes one audit line
per tools/call (caller, tool, employee id), and enforces scoped tokens.

The token comes from the GATEWAY_TOKEN environment variable only (no default in source).
Routing is built from each server's own tools/list, so no tool names are hardcoded here
except in the token scope table, which is policy, not plumbing.
"""
import sys
import os
import json
import datetime
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT_LOG_FILE = "audit.log"
GATEWAY_SERVER_INFO = {"name": "enterprise-mcp-gateway", "version": "1.0.0"}
DOWNSTREAM = ["policy_server.py", "hris_server.py"]

# token -> tools it may NOT call. Unknown tokens are rejected outright.
TOKEN_DENIED_TOOLS = {
    "SCOPED_LEAVE_ONLY_TOKEN": {"get_employee_grade_band"},
    "APPRAISAL_TOKEN": set(),
}

PROCS = {}          # script name -> Popen
TOOL_ROUTE = {}     # tool name -> script name
_next_id = 100


def _rpc(script: str, method: str, params: dict = None):
    global _next_id
    _next_id += 1
    msg = {"jsonrpc": "2.0", "id": _next_id, "method": method}
    if params is not None:
        msg["params"] = params
    proc = PROCS[script]
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def init_downstream():
    for script in DOWNSTREAM:
        PROCS[script] = subprocess.Popen(
            [sys.executable, os.path.join(HERE, script)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        _rpc(script, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                    "clientInfo": {"name": "gateway", "version": "1.0"}})
        PROCS[script].stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        PROCS[script].stdin.flush()
        for tool in _rpc(script, "tools/list").get("result", {}).get("tools", []):
            TOOL_ROUTE[tool["name"]] = script


def log_audit(caller: str, tool_name: str, emp_id: str, status: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[AUDIT] {timestamp} | caller: {caller} | tool: {tool_name} | "
                f"emp_id: {emp_id or 'N/A'} | status: {status}\n")


def _tool_result(msg_id, text: str, is_error: bool):
    return {"jsonrpc": "2.0", "id": msg_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": is_error}}


def process_message(msg: dict, token: str):
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": GATEWAY_SERVER_INFO}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        tools = []
        for script in DOWNSTREAM:
            tools += _rpc(script, "tools/list").get("result", {}).get("tools", [])
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})
        caller = args.pop("_caller", "agent-policy-assistant")
        emp_id = args.get("emp_id", "")

        if token not in TOKEN_DENIED_TOOLS:
            log_audit(caller, tool_name, emp_id, "DENIED (UNKNOWN_TOKEN)")
            return _tool_result(msg_id, "Recoverable Error: Permission Denied. The gateway token is "
                                        "not recognised. Ask People Ops for a valid scoped token.", True)
        if tool_name in TOKEN_DENIED_TOOLS[token]:
            log_audit(caller, tool_name, emp_id, "DENIED (UNAUTHORIZED_SCOPE)")
            allowed = sorted(t for t in TOOL_ROUTE if t not in TOKEN_DENIED_TOOLS[token])
            return _tool_result(
                msg_id,
                f"Recoverable Error: Permission Denied. Your token '{token}' is not scoped for "
                f"'{tool_name}'. Do not retry this tool. Tools your token can call: {', '.join(allowed)}.",
                True)
        if tool_name not in TOOL_ROUTE:
            log_audit(caller, tool_name, emp_id, "DENIED (UNKNOWN_TOOL)")
            return _tool_result(msg_id, f"Unknown tool: {tool_name}", True)

        log_audit(caller, tool_name, emp_id, "ALLOWED")
        downstream = _rpc(TOOL_ROUTE[tool_name], "tools/call", {"name": tool_name, "arguments": args})
        return {"jsonrpc": "2.0", "id": msg_id, "result": downstream.get("result", {})}

    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}}


def main():
    token = os.environ.get("GATEWAY_TOKEN")
    if not token:
        sys.stderr.write("GATEWAY_TOKEN is not set; refusing to start.\n")
        sys.exit(2)
    init_downstream()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            res = process_message(json.loads(line), token)
            if res is not None:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Gateway error: {e}\n")


if __name__ == "__main__":
    main()
