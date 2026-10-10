# Week 9 and Week 10: what each is, the flow, and live examples

All outputs below were captured from real runs on this machine (local Ollama llama3.2). Run everything from the repo root, using system `python` (the project venv is broken).

---
## 1. The one-line story
- **Week 9 (MCP):** give ONE agent tools that it *discovers at runtime* from servers listed in a config file. Nothing is hardcoded. Adding a server is a config change.
- **Week 10 (Multi-agent / A2A):** ask whether a *team* of agents (manager + 2 specialists) beats that single agent. Measure it. Ours lost, so we keep the single agent.

Week 10 builds on Week 9: both arms use the same kind of tools (policy search plus HRIS lookups).

---
## 2. Week 9 flow: dynamic MCP agent

```
config/mcp_servers.json
   |  (list of servers: command + args)
   v
MCPAgent.load_servers_from_config()
   |  spawn each server as a stdio subprocess (src/mcp_client.py, JSON-RPC)
   |  call initialize -> tools/list on each
   v
tools_registry  = { search_policy, get_policy_summary,          <- policy_server.py (Server 1)
                    get_employee_grade_band, get_accrued_leave_balance }  <- hris_server.py (Server 2)
   |
   v
MCPAgent.run(query)
   |  send discovered tool SCHEMAS to Ollama (native tool-calling)
   |  loop: model picks tool -> agent calls it over MCP -> result goes back to the model
   |  if a tool returns "Recoverable Error", the model re-calls with corrected args
   |  if Ollama is down: schema-driven fallback planner (no tool names in code)
   v
final answer + trace
```
Key points: tools come from `tools/list`, not from code; the model runs in the host, not in the servers; resources (handbook) are attached as context, not tools; `mcp_servers/gateway.py` adds audit log and scoped tokens (bonus).

### Example 1: discovery and a two-server query
```
python -m src.mcp_agent config/mcp_servers.json "What is the grade band and accrued leave balance for EMP001?"
[Agent] Active Discovered Tools (4): ['search_policy','get_policy_summary','get_employee_grade_band','get_accrued_leave_balance']
[Agent] Action -> 'get_employee_grade_band' {'emp_id':'EMP001'} on server 'hris_server'
[Agent] Observation: ... EMP001 (Alice Smith) is in Grade Band: L4 - Senior Associate ...
[Agent] Action -> 'get_accrued_leave_balance' {'emp_id':'EMP001'} on server 'hris_server'
[Agent] Observation: ... accrued leave balance of 10.0 days.
```
**Honest note:** in LLM mode the 3B model's final sentence was garbled ("Recoverable Error: Unable to retrieve...") even though both tool results were correct. The deterministic fallback shows the clean result:
```
MCP_AGENT_NO_LLM=1 python -m src.mcp_agent config/mcp_servers.json "...EMP001?"
Final Answer: EMP001 (Alice Smith) is in Grade Band: L4 - Senior Associate (Department: Engineering). ... accrued leave balance of 10.0 days.
```
Use the fallback run if you need a guaranteed-clean live demo.

### Example 2: Recoverable Error self-correction
```
python -m src.mcp_agent config/mcp_servers.json "What was the annual leave policy effective 2023-01-01?"
Action -> search_policy {'effective_date':'2023-01-01','query':'annual leave'}
Observation: Recoverable Error: No policy version effective 2023-01-01: earliest available is 2024-04-01. Please re-query using effective_date='2024-04-01' or later.
Final Answer: Since the earliest available policy version is 2024-04-01 ... 1.5 days per month up to 18 days per year. Unused leave up to 5 days can carry forward.
```
The error message itself told the agent how to recover.

### Example 3: config-only change (before/after)
```
config/mcp_servers_single.json  -> Active Discovered Tools (2): ['search_policy','get_policy_summary']
config/mcp_servers.json         -> Active Discovered Tools (4): + get_employee_grade_band, get_accrued_leave_balance
```
Two tools became four by adding one config entry. No agent code changed (`agent_diff.txt`, `config_diff.txt`, `tool_counts.txt` are the evidence files).

---
## 3. Week 10 flow: single agent vs orchestrator + 2 workers

```
                       SAME question, SAME tools, SAME judge
          ┌────────────────────────┴─────────────────────────┐
   SINGLE AGENT                                     MULTI (orchestrator)
   user -> agent (3 tools)                          1. user -> orchestrator: DECOMPOSE (JSON plan)
   loop: search / HRIS calls                        2. orchestrator -> POLICY WORKER (search tool only)
   -> final answer                                  3. orchestrator -> ELIGIBILITY WORKER (HRIS tools only,
                                                       only if plan says so; needs step 2's output,
                                                       so it runs AFTER, not in parallel)
                                                    4. workers -> orchestrator: SYNTHESIS
          └────────────────────────┬─────────────────────────┘
                                   v
            every LLM call logged as a hand-off row with real token counts
                                   v
   judge -> pass/fail; then p50/p99, tokens, cost, re-send multiplier, failure injection, verdict
```
Run commands:
```
python week10_race.py --smoke "question"   # wiring check on a NON-eval question
python week10_race.py                      # official race on Week-6 Q1-Q10 (about 10 min)
python week10_race.py --failure            # inject HTTP 500 into the policy worker on Q1
```

### Example 4: the race result
```
Pass rate   single 7/10    multi 5/10
p50 / p99   13.7 / 22.0 s   40.7 / 52.3 s
Tokens      10,348          17,763   -> 1.7x re-send multiplier
Cost/q      $0.00136        $0.00288 (reference price, real cost is $0)
Biggest hand-off: orchestrator -> policy_worker, 58% of multi tokens
```

### Example 5: the failure injection (500 on the policy worker, Q1)
```
policy worker: tool -> "HTTP 500 Internal Server Error" -> no retry -> "NO RELEVANT POLICY FOUND"
orchestrator answer: "I cannot answer this because the uploaded documents do not contain the required information."
```
Outcome: degraded (no retry, no invention), but it reported an outage as missing content.

### Example 6: why hand-offs hurt (live demo, a non-eval question with an employee ID)
Question: "Can EMP001 take annual leave? What is their grade band and accrued leave balance?"

| | Single | Multi |
|---|---|---|
| Time / tokens | 20.3 s / 1,125 | 63.1 s / 2,685 |
| Answer | "...grade band L4 - Senior Associate... accrued leave balance of 10.0 days." (correct) | "...grade band is not specified... accrued leave balance is in excess of 240 hours..." (wrong) |

In the multi run the decomposer correctly set `needs_eligibility=true, employee_id=EMP001`, but the eligibility worker's report ("eligible to take annual leave") dropped the grade band and balance. The synthesiser then filled the gap with a "240 hours" figure taken from a military-leave passage. Facts were lost at the hand-off, and a wrong number was produced. This is the practical meaning of "every hand-off re-sends context and can degrade it". It is one illustrative run, not part of the 10-case measurement.

---
## 4. How Week 9 and Week 10 connect
| | Week 9 | Week 10 |
|---|---|---|
| Question | How does an agent get tools without hardcoding? | Is a team of agents better than one agent? |
| Protocol | MCP (agent <-> tool) | A2A idea (agent <-> agent); AgentCard in `week10/agentcard.json` |
| Result | 4 tools discovered from config, errors self-correct | Multi lost on pass rate, latency, tokens and cost |
| Decision | Keep dynamic discovery | Keep the single agent; revisit only for parallel or differently-instructed work |

## 5. Suggested live-demo order (about 5 minutes)
1. Week 9 Example 3: show the two configs and the 2 -> 4 tool count.
2. Week 9 Example 2: the Recoverable Error recovery.
3. Week 9 Example 1 with `MCP_AGENT_NO_LLM=1` for a clean answer.
4. Week 10: open `week10/race_table.md`, then `handoffs.log` for the 58% hand-off.
5. Week 10 Example 6 (`--smoke` with the EMP001 question) to show the lost-facts failure live.
6. Close with `week10/verdict.md`: sunk cost named, then kill.
