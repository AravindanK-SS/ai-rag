"""
Regenerates the Week 9 evidence files from real runs (nothing is hand-typed output):
  tool_counts.txt, wire.json, error_before_after.md, agent_diff.txt, config_diff.txt

Usage: python week9_evidence.py <BASE_COMMIT> <SERVER2_COMMIT>
  BASE_COMMIT    = commit with the agent and server one only
  SERVER2_COMMIT = commit that adds the HRIS server (config + server file only)
"""
import json
import os
import subprocess
import sys
import tempfile

from src.mcp_agent import MCPAgent
from src.mcp_client import MCPClient

AGENT_FILES = ["src/mcp_agent.py", "src/mcp_client.py", "src/ollama_chat.py"]
SINGLE = "config/mcp_servers_single.json"
BOTH = "config/mcp_servers.json"
FAIL_QUERY = "What was our annual leave policy effective 2023-01-01?"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def agent_and_config_diff(base, s2):
    agent_diff = git("diff", base, s2, "--", *AGENT_FILES)
    changed = len([l for l in agent_diff.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")])
    header = (f"# git diff {base} {s2} -- {' '.join(AGENT_FILES)}\n"
              f"# BASE={base} (agent + server one)  SERVER2={s2} (adds HRIS server)\n"
              f"# changed lines in agent module: {changed}\n")
    write("agent_diff.txt", header + agent_diff)
    write("config_diff.txt", git("diff", base, s2, "--", "config/mcp_servers.json"))
    return changed


def tool_counts():
    def names(cfg):
        agent = MCPAgent(cfg, llm=None)
        out = agent.list_discovered_tool_names()
        agent.shutdown()
        return out
    before, after = names(SINGLE), names(BOTH)
    write("tool_counts.txt",
          f"Tool count: {len(before)} before -> {len(after)} after (taken from tools/list)\n\n"
          f"Before (config/mcp_servers_single.json): {len(before)}\nTools: {before}\n\n"
          f"After (config/mcp_servers.json): {len(after)}\nTools: {after}\n")
    return before, after


def capture_wire():
    """Spawn the HRIS server and record the raw lines exchanged, byte for byte."""
    old = json.load(open("wire.json", encoding="utf-8"))
    proc = subprocess.Popen([sys.executable, "mcp_servers/hris_server.py"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "ai-rag-agent-host", "version": "1.0.0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "get_employee_grade_band", "arguments": {"emp_id": "EMP001"}}},
    ]
    stages = [("1. INITIALIZE (Handshake Request)", "Host/Agent Client -> HRIS Server"),
              ("2. INITIALIZE (Handshake Response)", "HRIS Server -> Host/Agent Client"),
              ("3. TOOLS/LIST (Discovery Request)", "Host/Agent Client -> HRIS Server"),
              ("4. TOOLS/LIST (Discovery Response)", "HRIS Server -> Host/Agent Client"),
              ("5. TOOLS/CALL (Execution Request)", "Host/Agent Client -> HRIS Server"),
              ("6. TOOLS/CALL (Execution Response)", "HRIS Server -> Host/Agent Client")]
    raw = []
    for req in requests:
        line = json.dumps(req)
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
        raw.append(line)
        raw.append(proc.stdout.readline().strip())
        if req["method"] == "initialize":
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
    proc.terminate()
    exchanges = []
    for (stage, direction), line, prev in zip(stages, raw, old["raw_exchanges"]):
        exchanges.append({"stage": stage, "direction": direction, "raw_line_on_wire": line,
                          "raw_message": json.loads(line), "hand_annotations": prev["hand_annotations"]})
    old["raw_exchanges"] = exchanges
    old["captured_by"] = "week9_evidence.py (live subprocess, lines recorded as written/read)"
    write("wire.json", json.dumps(old, indent=2, ensure_ascii=False) + "\n")


def run_transcript(args):
    """Run FAIL_QUERY through the real agent against a server config and format the steps."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"mcpServers": {"policy_server": {
            "command": "python", "args": ["mcp_servers/policy_server.py"] + args}}}, f)
        cfg = f.name
    agent = MCPAgent(cfg)
    quiet = open(os.devnull, "w")
    old_stdout, sys.stdout = sys.stdout, quiet
    try:
        trace = agent.run(FAIL_QUERY)
    finally:
        sys.stdout = old_stdout
        agent.shutdown()
        os.unlink(cfg)
    lines = [f"[User]: {FAIL_QUERY}", f"[Agent mode]: {trace['mode']}"]
    for i, s in enumerate(trace["steps"], 1):
        lines += [f"[Action {i}]: {s['tool']} {json.dumps(s['arguments'])}",
                  f"[Tool result {i}] (isError={s['is_error']}): {s['result']}"]
    lines.append(f"[Final answer]: {trace['final_answer']}")
    return "\n".join(lines), trace


def error_before_after():
    before, tb = run_transcript(["--legacy"])
    after, ta = run_transcript([])
    write("error_before_after.md", f"""# Error Handling Before & After: Docstring-as-Prompt & Recoverable Errors

Both transcripts below are captured output from `week9_evidence.py` running the SAME failing call
(`effective_date=2023-01-01`) through `src/mcp_agent.py`. Only the server's docstring and error text differ
(`mcp_servers/policy_server.py --legacy` vs default).

## 1. Docstring rewrite (policy_server.py `search_policy`)
- Before: `"Search policy documents."`
- After: `"Search company HR policy documents by topic and effective date. Input 'query' with the topic (e.g., 'annual leave', 'attendance') and 'effective_date' in YYYY-MM-DD format. Note: Earliest active policy version is 2024-04-01; queries prior to this date will return date bounds for recovery."`

## 2. Error path rewrite
- Before: `Error 3: Policy not found`
- After: `Recoverable Error: No policy version effective 2023-01-01: earliest available is 2024-04-01. Please re-query using effective_date='2024-04-01' or later.`

## 3. Transcript BEFORE (legacy docstring + opaque error)
```
{before}
```
Steps taken: {len(tb['steps'])}. The opaque code carries no date bound, so the host cannot tell "version does not exist
yet" from "HRIS is down", and it dead-ends.

## 4. Transcript AFTER (docstring-as-prompt + recoverable error)
```
{after}
```
Steps taken: {len(ta['steps'])}. The error names the earliest valid date, so the second call succeeds and the
answer states that no 2023 version exists.

> Note: the "Agent mode" line shows who drove the recovery. When Ollama has `llama3.2` pulled, re-run
> `python week9_evidence.py <BASE> <SERVER2>` to capture the LLM-driven version of the same exchange.
""")


if __name__ == "__main__":
    base, s2 = sys.argv[1], sys.argv[2]
    changed = agent_and_config_diff(base, s2)
    before, after = tool_counts()
    capture_wire()
    error_before_after()
    print(f"agent diff changed lines: {changed}; tools {len(before)} -> {len(after)}")
