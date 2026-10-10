# failure_case.md: injected 500 on the policy-retrieval worker

**Case:** Q1 "What is the policy for annual leave?" (a separate run; it is not part of the 10-case race numbers).
**Injection:** `search_policy_docs` raised `HTTP 500 Internal Server Error: policy retrieval backend failed` on every call in that run.

What happened, from `failure_raw.json`:
1. Orchestrator decomposed correctly (`policy_query="annual leave policy"`, no eligibility needed).
2. Policy worker called the tool once, got the 500 as its tool message, and did **not retry**. It reported `NO RELEVANT POLICY FOUND`.
3. The orchestrator forwarded that to synthesis and answered with the standard refusal: "I cannot answer this because the uploaded documents do not contain the required information."
4. No number or notice period was invented (check: 0 digits in the answer that no tool returned).

**One-line verdict: the orchestrator DEGRADED to a refusal. It did not retry and it did not lie, but it misreported an outage as "the documents don't contain it", so the employee is never told the service failed.**

Bounded retry plus an explicit "policy service unavailable" status is not in the orchestrator as built; the worker flattened the 500 into a content statement. The single agent, run on the same fault, gave the identical refusal and also did not retry, so this is not a multi-agent-specific flaw. It is just invisible in the multi arm because the error crosses one more hand-off.
