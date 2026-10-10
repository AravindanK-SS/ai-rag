# verdict.md
Sunk-cost bias, said out loud: I spent a week building the orchestrator, and I want it to win. That is the sunk cost talking, not the data.
Pass rate: single 7/10 vs multi 5/10 (same 10 Week-6 cases, same judge, one pass each, no re-runs).
Latency p50: 13.7 s vs 40.7 s (3.0x slower; eligibility depends on retrieval, so this task does not parallelise).
Tokens: 10,348 vs 17,763 = 1.7x re-send multiplier; 58% of multi tokens are the orchestrator -> policy_worker hand-off. Cost/question $0.00136 vs $0.00288 (2.1x, reference price).
Multi lost on all four numbers; its worst new failure: on Q3 the decomposer sent an ID-less question to the eligibility worker, which queried HRIS for "NONE" and the answer became "No one is eligible".
VERDICT: KILL the orchestrator for this task; keep the single agent. n=10 and a 3B self-judge are noisy, so 7 vs 5 is a direction, not proof.
Revisit only when a question genuinely needs HRIS data for a named employee (different instructions, independent lookups), and re-race it.
