# Bonus: A2A mapping (AgentCard is in agentcard.json)

**Failed case (Q1, policy worker 500):** the task should end in `failed`, after one bounded retry with backoff (a 5xx is transient). It should NOT pause at `input-required`: nothing is missing from the employee. `input-required` is correct only when the employee's grade band or ID is genuinely unknown and HRIS cannot supply it; then the orchestrator pauses and asks them. The as-built agent ended in `completed` with a misleading refusal, which is the wrong state.

**What A2A buys over a plain REST call to the worker (two lines):**
1. A discoverable contract (AgentCard: skills, modes, auth) plus a standard task lifecycle (submitted, working, input-required, failed, completed), so a failure or a question back to the user is a first-class state instead of a flattened string.
2. Workers can be owned and swapped by other teams or vendors with no custom glue. For one team and two in-process workers, as here, plain function calls would do.

MCP connects an agent to tools; A2A connects an agent to other agents.
