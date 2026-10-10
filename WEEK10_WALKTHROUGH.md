# Week 10 walkthrough: Multi-agent and A2A, with evidence

## 1. The topics this week covers
- **Orchestrator-worker:** a manager agent splits the question and hands pieces to specialists, then synthesises. Here: decompose, policy worker, eligibility worker, synthesis.
- **Specialist agents:** narrow prompt plus fewer tools. The policy worker only has `search_policy_docs`; the eligibility worker only has the two HRIS tools. The single agent has all three. Narrow prompts and fewer tools are the one plausible source of a multi-agent win.
- **When multi-agent helps:** truly independent sub-tasks that can run in parallel, or tasks that need clearly different instructions. Here eligibility depends on the retrieved policy, so nothing parallelises.
- **Context re-send cost:** each hand-off sends a fresh prompt (system prompt, question, prior worker output), so the same content is paid for again at every hop.
- **Fair race:** same cases, same judge, same tools, one pass, no re-runs. Report four numbers: quality, latency (p50/p99), tokens, cost.
- **A2A:** agent-to-agent protocol. MCP = agent to tools; A2A = agent to agents. An **AgentCard** advertises skills, modes and auth; a **task lifecycle** (submitted, working, input-required, failed, completed) makes failures and questions first-class.
- **CrewAI / AutoGen:** frameworks that package this pattern. This week the pattern is hand-rolled so every token can be counted.
- **Sunk-cost bias:** keeping a system because you built it, not because it wins.

## 2. What we did, step by step
1. Read both briefs (Task Set C and the Module 5 brief). Found that no Week 10 orchestrator existed in the repo, so it had to be built.
2. Found the project venv dead (its interpreter was on another machine) and system Python lacking langchain/chroma. The chunk text and `source_file` metadata are readable directly from `vectorstore/current/chroma.sqlite3`, so `src/chunk_search.py` is a BM25 retriever over them. Both arms use it.
3. `src/w10_tools.py`: one shared tool layer (policy search, plus the existing HRIS handlers) with per-run recording of what was retrieved, and a switch that injects an HTTP 500.
4. `src/w10_agents.py`: a metered Ollama client (real `prompt_eval_count` + `eval_count`; verified stable across repeated calls), the single agent, and the orchestrator with two workers. Every LLM call is logged as a hand-off row.
5. `week10_race.py`: the runner, one judge for both arms, and the failure mode. Wiring was smoke-tested on a question outside the eval set. Prompts were frozen before the official run.
6. Official race on Week-6 cases Q1 to Q10, verbatim: one pass per arm, no re-runs, alternating arm order, model warmed up first.
7. Failure run: 500 on `search_policy_docs` for Q1, on both arms.
8. Wrote the deliverables in `week10/`: race_table.md, handoffs.log, failure_case.md, verdict.md, plus bonus agentcard.json and a2a_mapping.md.

## 3. Results
| | Single | Multi |
|---|---|---|
| Pass | 7/10 | 5/10 |
| p50 / p99 | 13.7 / 22.0 s | 40.7 / 52.3 s |
| Tokens | 10,348 | 17,763 (1.7x) |
| Cost/question (reference price) | $0.00136 | $0.00288 |

Largest token share: orchestrator -> policy_worker, 58%. Failure injection: the orchestrator degraded to a refusal, with no retry and no invention, but it hid the outage. Verdict: KILL the orchestrator for this task.

## 4. Caveats
- n=10, one run per arm, and a 3B model judging itself. Treat 7 vs 5 as a direction.
- BM25 instead of the Week 5 dense retriever. This lowers absolute pass rates equally for both arms; Q2 and Q7 failed for both.
- Cost uses a hosted reference price (assumption). The real local cost is $0.
- Most Week-6 cases do not need eligibility. That is part of why multi has nothing to win with here.
- Nothing is committed to git.
