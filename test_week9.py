"""
Week 9 Comprehensive Test Runner
Tests all requirements of Week 9 Task Set C:
1. Dynamic Tool Discovery (Before vs After)
2. Agent query execution provably calling HRIS tools
3. Recoverable Error vs Legacy Error path
4. Zero-line diff verification
5. Bonus Gateway & Scoped Token Authorization
"""
import sys
import os
import json
import subprocess
from src.mcp_client import MCPClient
from src.mcp_agent import MCPAgent

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_1_tool_discovery():
    print_header("TEST 1: DYNAMIC TOOL DISCOVERY (BEFORE vs AFTER)")
    
    # Server 1 only
    client1 = MCPClient("policy_server", sys.executable, ["mcp_servers/policy_server.py"])
    client1.start()
    tools_before = [t["name"] for t in client1.list_tools()]
    client1.stop()
    print(f"[✓] Server 1 Discovery: {len(tools_before)} tools found -> {tools_before}")
    assert len(tools_before) == 2, f"Expected 2 tools, got {len(tools_before)}"
    
    # Server 2 (HRIS)
    client2 = MCPClient("hris_server", sys.executable, ["mcp_servers/hris_server.py"])
    client2.start()
    tools_hris = [t["name"] for t in client2.list_tools()]
    client2.stop()
    print(f"[✓] Server 2 Discovery: {len(tools_hris)} tools found -> {tools_hris}")
    assert len(tools_hris) == 2, f"Expected 2 tools, got {len(tools_hris)}"
    
    total_after = tools_before + tools_hris
    print(f"\n>> RESULT: Tool count line: {len(tools_before)} before -> {len(total_after)} after")
    print(">> TEST 1 PASSED ✅\n")

def test_2_agent_query_execution():
    print_header("TEST 2: AGENT QUERY EXECUTING HRIS TOOLS")
    
    agent = MCPAgent(config_path="config/mcp_servers.json")
    query = "What is the grade band and accrued leave balance for employee EMP001?"
    trace = agent.run(query)
    agent.shutdown()
    
    called_tools = [step["tool"] for step in trace["steps"]]
    print(f"[✓] Query: {query}")
    print(f"[✓] Discovered Tools in Agent: {trace['discovered_tools']}")
    print(f"[✓] Tools Provably Called: {called_tools}")
    print(f"[✓] Final Answer: {trace['final_answer']}")
    
    assert "get_employee_grade_band" in called_tools, "get_employee_grade_band was not called"
    assert "get_accrued_leave_balance" in called_tools, "get_accrued_leave_balance was not called"
    print(f"[✓] Agent mode: {trace['mode']}")
    observed = " ".join(step["result"] for step in trace["steps"])
    assert "L4 - Senior Associate" in observed, "Expected grade band in tool results"
    assert "10.0 days" in observed, "Expected leave balance in tool results"
    print(">> TEST 2 PASSED ✅\n")

def test_3_recoverable_error():
    print_header("TEST 3: RECOVERABLE ERROR PATH (DATE < 2024-04-01)")
    
    client = MCPClient("policy_server", sys.executable, ["mcp_servers/policy_server.py"])
    client.start()
    
    # Call with pre-2024 date
    res = client.call_tool("search_policy", {"query": "annual leave", "effective_date": "2023-01-01"})
    client.stop()
    
    err_text = res.get("content", [{}])[0].get("text", "")
    is_error = res.get("isError", False)
    print(f"[✓] Calling search_policy with effective_date='2023-01-01'")
    print(f"[✓] Is Error Flag: {is_error}")
    print(f"[✓] Tool Response: {err_text}")
    
    assert is_error is True, "Expected isError=True"
    assert "Recoverable Error" in err_text, "Expected 'Recoverable Error' in message"
    assert "2024-04-01" in err_text, "Expected date bound '2024-04-01' in recovery message"
    print(">> TEST 3 PASSED ✅\n")

def test_4_zero_line_diff():
    print_header("TEST 4: ZERO CHANGED LINES IN AGENT MODULE")

    with open("agent_diff.txt", "r", encoding="utf-8") as f:
        header = f.read().splitlines()[0]
    # header: "# git diff <BASE> <SERVER2> -- <files...>"
    parts = header.split()
    base, server2, files = parts[3], parts[4], parts[6:]
    live = subprocess.run(["git", "diff", base, server2, "--", *files],
                          capture_output=True, text=True, check=True).stdout
    print(f"[✓] Re-ran: git diff {base} {server2} -- {' '.join(files)}")
    print(f"[✓] Live diff length: {len(live)} characters")
    assert live == "", f"Agent module changed between server one and server two: {live}"

    cfg_diff = open("config_diff.txt", "r", encoding="utf-8").read()
    print("[✓] config_diff.txt adds 'hris_server':")
    for line in cfg_diff.splitlines():
        if line.startswith("+") or line.startswith("-"):
            print(f"    {line}")
    assert "hris_server" in cfg_diff

    print(">> TEST 4 PASSED ✅\n")

def test_5_bonus_gateway():
    print_header("TEST 5: BONUS GATEWAY & SCOPED AUTHORIZATION")
    
    # Test through Gateway with scoped token
    proc = subprocess.Popen(
        [sys.executable, "mcp_servers/gateway.py"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        env={**os.environ, "GATEWAY_TOKEN": "SCOPED_LEAVE_ONLY_TOKEN"}
    )
    
    # Initialize
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}
    }) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()
    
    # 1. Allowed call: get_accrued_leave_balance
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "get_accrued_leave_balance", "arguments": {"emp_id": "EMP001"}}
    }) + "\n")
    proc.stdin.flush()
    res1 = json.loads(proc.stdout.readline())
    text1 = res1.get("result", {}).get("content", [{}])[0].get("text", "")
    print(f"[✓] Gateway Leave Balance (ALLOWED): {text1}")
    assert "10.0 days" in text1
    
    # 2. Denied call: get_employee_grade_band (Denied for scoped token)
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "get_employee_grade_band", "arguments": {"emp_id": "EMP001"}}
    }) + "\n")
    proc.stdin.flush()
    res2 = json.loads(proc.stdout.readline())
    text2 = res2.get("result", {}).get("content", [{}])[0].get("text", "")
    print(f"[✓] Gateway Grade Band (DENIED): {text2}")
    assert "Permission Denied" in text2
    assert "SCOPED_LEAVE_ONLY_TOKEN" in text2
    
    proc.terminate()

    # Denial reaching the agent (model host) as a recoverable message, via the single front door
    agent = MCPAgent(config_path="config/mcp_servers_gateway.json")
    trace = agent.run("What is the grade band of employee EMP001?")
    agent.shutdown()
    denied = [st for st in trace["steps"] if st["is_error"]]
    print(f"[✓] Agent via gateway, tools seen: {trace['discovered_tools']}")
    print(f"[✓] Denial observed by agent: {denied[0]['result'] if denied else None}")
    assert denied and "Permission Denied" in denied[0]["result"]
    assert "get_accrued_leave_balance" in denied[0]["result"]

    audit = open("audit.log", encoding="utf-8").read()
    assert "DENIED (UNAUTHORIZED_SCOPE)" in audit and "ALLOWED" in audit
    print(">> TEST 5 PASSED ✅\n")

if __name__ == "__main__":
    test_1_tool_discovery()
    test_2_agent_query_execution()
    test_3_recoverable_error()
    test_4_zero_line_diff()
    test_5_bonus_gateway()
    
    print("=" * 70)
    print("  ALL 5 WEEK 9 TESTS COMPLETED SUCCESSFULLY! (100% PASS) 🎉")
    print("=" * 70)
