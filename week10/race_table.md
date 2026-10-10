# Race table: single agent vs orchestrator + 2 workers

Cases: Week-6 `results/test_cases_week6.json` Q1-Q10, verbatim: Q1 What is the policy for annual leave?; Q2 What are the core work hours?; Q3 Who is eligible for internet reimbursement?; Q4 How many vacation days do faculty members get?; Q5 Can I take educational leave?; Q6 What happens if I am late to work 3 times?; Q7 Is maternity leave paid?; Q8 How do I apply for a promotion?; Q9 What is the dress code for casual Fridays?; Q10 Can I bring my dog to the office?.

| Metric | Single agent | Multi (orchestrator + 2 workers) |
|---|---|---|
| Pass rate (same judge) | 7/10 (70%) | 5/10 (50%) |
| Latency p50 | 13.7 s | 40.7 s |
| Latency p99 (linear interp., n=10, so about the max) | 22.0 s | 52.3 s |
| Total tokens (prompt + completion) | 10348 (9535 + 813) | 17763 (15014 + 2749) |
| Cost per question (reference $1.00 in / $5.00 out per 1M tokens) | $0.001360 | $0.002876 |

**Context re-send multiplier: 1.7x (multi 17763 tokens / single 10348 tokens). Largest share: orchestrator -> policy_worker, 58% of all multi-arm tokens.**

Per-case detail:

| Case | Single | s | tok | Multi | s | tok |
|---|---|---|---|---|---|---|
| Q1 | PASS | 16.7 | 1042 | PASS | 45.3 | 1635 |
| Q2 | FAIL | 9.8 | 954 | FAIL | 27.2 | 1344 |
| Q3 | PASS | 11.8 | 1008 | FAIL | 52.1 | 2516 |
| Q4 | PASS | 14.2 | 1065 | PASS | 39.7 | 1657 |
| Q5 | PASS | 14.6 | 1019 | PASS | 52.3 | 2546 |
| Q6 | PASS | 14.8 | 1068 | PASS | 41.7 | 1624 |
| Q7 | FAIL | 13.2 | 1107 | FAIL | 32.3 | 1544 |
| Q8 | FAIL | 22.5 | 1087 | FAIL | 46.1 | 2395 |
| Q9 | PASS | 12.3 | 1014 | FAIL | 29.1 | 1383 |
| Q10 | PASS | 10.1 | 984 | PASS | 17.0 | 1119 |

Method notes (read before trusting the numbers):
- One pass per arm. No re-runs. Prompts frozen before the run. Arm order alternated per case.
- Model: local Ollama llama3.2 (3B). Tokens are Ollama's own prompt_eval_count + eval_count. Real cost is $0; the dollar figure applies a hosted reference price (assumption, adjustable in week10_race.py).
- Judge: Week 6 labels as rules (generation cases must refuse; retrieval cases must retrieve the expected PDF and not refuse) plus an LLM groundedness/answers check by the same llama3.2. Judge tokens are excluded from both arms. A 3B self-judge is noisy; see results_raw.json to audit every verdict.
- Retriever: BM25 over the persisted Chroma chunks (src/chunk_search.py), same for both arms, because the project venv is dead on this machine. Absolute pass rate is below the Week 5 dense retriever.
- Eligibility depends on the retrieved policy, so the orchestrator runs workers sequentially; this task does not parallelise.
