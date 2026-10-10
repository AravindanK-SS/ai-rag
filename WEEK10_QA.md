# Week 10 Q&A: topics and practical questions with answers

Numbers come from our real run (`week10/race_table.md`): Week-6 Q1-Q10, one pass per arm, local llama3.2, BM25 retriever.

---
## Part A. Topics covered, each with a short answer

**1. Orchestrator-worker.** One manager agent splits the question, delegates pieces to specialist agents, and synthesises their reports. Ours: decompose -> policy worker -> (optional) eligibility worker -> synthesis.

**2. Specialist agents.** A worker gets a narrow system prompt and only the tools its job needs. Policy worker: `search_policy_docs` only. Eligibility worker: the two HRIS tools only. The single agent has all three. Narrow prompt plus fewer tools is the only plausible source of a multi-agent quality win.

**3. When multi-agent helps.** (a) Sub-tasks are truly independent and can run in parallel, or (b) sub-tasks need clearly different instructions or tool sets. It does not help when step 2 depends on step 1 (ours: eligibility needs the retrieved policy).

**4. Context re-send cost.** Every hand-off is a new LLM call whose prompt carries the system prompt, the question, and earlier outputs again. Cost grows with the number of hops, not with the amount of new information.

**5. Single vs multi race.** Same cases, same judge, same tools and context budget, one pass per arm, no re-runs, order alternated. Changing any of these changes the ruler.

**6. Quality / latency / tokens / cost.** Report all four: pass rate, p50 and p99 latency, total tokens, cost per question. A win on one with a silent loss on another is not a result.

**7. A2A protocol.** Agent-to-Agent: a standard for one agent to hand a task to another across teams or vendors. MCP connects an agent to tools; A2A connects an agent to agents.

**8. AgentCard and task lifecycle.** The AgentCard is a JSON profile an agent advertises: name, url, skills, input/output modes, auth. The task lifecycle gives each delegated task a state: submitted -> working -> input-required / failed / completed (also canceled). See `week10/agentcard.json`.

**9. MCP vs A2A.** MCP: agent <-> tool/data (stateless-ish calls, schemas from `tools/list`). A2A: agent <-> agent (long-running tasks, states, can ask for more input). Week 9 was MCP; Week 10 is the layer above it.

**10. CrewAI / AutoGen.** Frameworks that package orchestrator-worker patterns (roles and tasks in CrewAI; conversational multi-agent in AutoGen). We hand-rolled the pattern so every token could be counted. The framework does not change the re-send economics.

**11. Sunk-cost bias.** Keeping something because you invested in it. Name it before the verdict, then decide on the numbers.

---
## Part B. Practical questions with answers

**Q1. Which cases do you race, and may you write new ones?**
The same 10 Week-6 cases: Q1-Q10 of `results/test_cases_week6.json`, verbatim. No new cases. A changed eval set voids the comparison.

**Q2. What are the four numbers for both arms?**

| | Single | Multi |
|---|---|---|
| Pass rate | 7/10 | 5/10 |
| p50 / p99 | 13.7 s / 22.0 s | 40.7 s / 52.3 s |
| Total tokens | 10,348 | 17,763 |
| Cost per question | $0.00136 | $0.00288 |

Cost applies a reference hosted price ($1 in / $5 out per 1M tokens, an assumption). The real local cost is $0. With n=10, p99 is effectively the max.

**Q3. How is the context re-send multiplier computed?**
multi tokens / single tokens = 17,763 / 10,348 = **1.7x**.

**Q4. Which hand-off carries the biggest token share?**
`orchestrator -> policy_worker`: 10,266 of 17,763 multi tokens = **58%**. It is the biggest because the policy worker's prompt contains the retrieved passages and is called twice (tool call, then the report). Next: synthesis 18%, eligibility worker 16%, decompose 8%. Source: `week10/handoffs.log`.

**Q5. You injected a 500 in the policy worker. What did the orchestrator do: retry, degrade, or lie?**
**Degraded.** The worker called the tool once, got the 500, did not retry, and reported `NO RELEVANT POLICY FOUND`. The orchestrator then returned the standard refusal. No invented numbers (0 digits in the answer that no tool returned). The flaw: it reported an outage as "the documents do not contain it". The single agent did the same.

**Q6. What is the keep-or-kill verdict, and which bias do you name?**
**Kill** the orchestrator for this task, keep the single agent. Bias named first: sunk cost (a week spent building it). Numbers cited: pass 5/10 vs 7/10, p50 40.7 s vs 13.7 s, tokens 1.7x, cost 2.1x. Caveat: n=10 and a 3B self-judge, so this is a direction, not proof.

**Q7. Why did multi lose Q3?**
The decomposer set `needs_eligibility=true` with no employee ID. The eligibility worker then queried HRIS for "NONE" and the final answer became "No one is eligible". This is an error that only exists because of the extra hand-off.

**Q8. Why does this task not parallelise?**
Eligibility depends on the retrieved policy, so the workers must run in sequence. Latency is therefore the sum of the calls (about 3x the single agent). The honest note is that the dependency is real, not a bug in the implementation.

**Q9. Bonus: should the failed case end `failed` or `input-required`?**
`failed`, after one bounded retry with backoff, because a 5xx is a service fault and nothing is missing from the employee. `input-required` would be right only if the employee's ID or grade band were unknown and HRIS could not supply it. Our system ended `completed` with a misleading refusal, which is the wrong state.

**Q10. What does A2A buy over a plain REST call to the worker?**
(1) A discoverable contract (AgentCard) and a standard lifecycle, so failures and questions back to the user are first-class states. (2) Workers owned by other teams or vendors can be swapped in with no custom glue. For two in-process workers owned by one team, plain function calls would suffice.

---
## Part C. Common mistakes and the answers

| Mistake | Why it is wrong | What we did |
|---|---|---|
| Declaring multi the winner on pass rate while ignoring a 9x token bill | Quality without cost hides the real price | Reported all four numbers in one table |
| Building a fresh eval set | Changes the ruler mid-measurement | Used Q1-Q10 verbatim |
| Giving both workers the whole handbook | Tests your context strategy, not the pattern | Top-3 passages, 600 chars each, same for both arms |
| Giving the eligibility worker every tool | Deletes the narrow-tools advantage | It has the two HRIS tools only |
| Running workers sequentially and blaming the pattern | The dependency is real | Stated that the task does not parallelise |
| Re-running multi until it wins | That is the sunk cost driving | One pass per arm, prompts frozen, loss reported |

---
## Part D. Mentor's Friday questions

1. **Same tests?** Yes: Week-6 Q1-Q10, same judge, same tools.
2. **All four numbers?** Yes: quality, speed, tokens, cost, for both arms.
3. **Verdict backed by numbers even though the team lost?** Yes: kill, citing pass rate, p50, tokens and cost.
4. **When is multi-agent worth it, and when not?**
   - Worth it: independent sub-tasks that parallelise, or sub-tasks needing really different instructions/tools, or workers owned by different teams (A2A). Re-race to confirm.
   - Not worth it: short, single-step lookups like these Week-6 questions, where the hand-offs only add re-sent context, latency and new failure points.
