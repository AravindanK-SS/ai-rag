"""
Week 10 Task Set C: race the policy squad (orchestrator + 2 workers) against the single agent.

  python week10_race.py --smoke "question"   # wiring check on a NON-eval question
  python week10_race.py                      # official race: Week-6 cases Q1-Q10, one pass per arm, no re-runs
  python week10_race.py --failure            # inject a 500 into the policy worker on one case

Run from the repo root. Needs Ollama + llama3.2.
"""
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from src.w10_agents import HandoffLog, Meter, REFUSAL, run_multi, run_single
from src.w10_tools import Toolbox

OUT = Path("week10")
CASES_FILE = "results/test_cases_week6.json"
N_CASES = 10                       # Week-6 cases Q1-Q10, taken verbatim, never edited
FAILURE_CASE_ID = 1                # Q1 "What is the policy for annual leave?"
# Reference hosted-model list price (USD per 1M tokens). ASSUMPTION: the real run is local llama3.2 = $0.
PRICE_IN, PRICE_OUT = 1.00, 5.00

JUDGE_SYSTEM = (
    "You are a strict judge. Given a question, the evidence the system retrieved, and its answer, reply "
    'with JSON only: {"grounded": <true if every factual claim in the answer is supported by the evidence>, '
    '"answers": <true if the answer directly addresses the question>, "why": "<one short sentence>"}'
)


def is_refusal(text: str) -> bool:
    t = text.lower()
    return "cannot answer this because" in t or "do not contain the required information" in t


def judge(llm: Meter, case: dict, result: dict, tb: Toolbox) -> dict:
    """Same judge for both arms. Rules first (Week 6 labels), then an LLM groundedness check."""
    ans = result["answer"]
    if case["type"] == "generation":          # Week 6: must fall back, not hallucinate
        ok = is_refusal(ans)
        return {"passed": ok, "why": "correct refusal" if ok else "answered instead of refusing"}
    if is_refusal(ans):
        return {"passed": False, "why": "false refusal on a retrieval case"}
    if case["expected_document"] not in tb.sources:
        return {"passed": False, "why": f"expected doc not retrieved (got {sorted(set(tb.sources))})"}
    evidence = "\n".join(tb.context)[:6000]
    msg, _ = llm.chat_usage([{"role": "system", "content": JUDGE_SYSTEM},
                             {"role": "user", "content": f"Question: {case['question']}\n\nEvidence:\n{evidence}"
                                                         f"\n\nAnswer:\n{ans}"}], fmt="json")
    try:
        j = json.loads(msg.get("content") or "{}")
    except json.JSONDecodeError:
        j = {}
    ok = bool(j.get("grounded")) and bool(j.get("answers"))
    return {"passed": ok, "why": j.get("why", "judge returned no JSON")}


def percentile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def cost(prompt_tokens, completion_tokens):
    return prompt_tokens / 1e6 * PRICE_IN + completion_tokens / 1e6 * PRICE_OUT


def run_arm(llm, log, arm, case_id, question, inject=None):
    tb = Toolbox(inject_500_on=inject)
    fn = run_single if arm == "single" else run_multi
    t0 = time.time()
    res = fn(llm, log, tb, case_id, question)
    return res, tb, round(time.time() - t0, 2)


def smoke(question):
    llm, log = Meter(), HandoffLog()
    for arm in ("single", "multi"):
        res, tb, secs = run_arm(llm, log, arm, "smoke", question)
        print(f"\n== {arm} ({secs}s, {log.total(arm, 'smoke')} tokens, tool_calls={len(tb.calls)})")
        print(json.dumps(res["reports"], indent=1)[:1500] if res["reports"] else "")
        print("ANSWER:", res["answer"])


def race():
    OUT.mkdir(exist_ok=True)
    cases = json.load(open(CASES_FILE, encoding="utf-8"))[:N_CASES]
    llm, log = Meter(), HandoffLog()
    llm.chat_usage([{"role": "user", "content": "hi"}])          # warm-up: neither arm eats the model load
    rows = defaultdict(list)
    raw = []
    for i, c in enumerate(cases):
        cid = f"Q{c['id']}"
        order = ("single", "multi") if i % 2 == 0 else ("multi", "single")   # alternate to cancel drift
        for arm in order:
            res, tb, secs = run_arm(llm, log, arm, cid, c["question"])
            verdict = judge(llm, c, res, tb)
            p, comp = log.split(arm, cid)
            rows[arm].append({"case": cid, "secs": secs, "prompt": p, "completion": comp,
                              "passed": verdict["passed"]})
            raw.append({"case": cid, "arm": arm, "question": c["question"], "answer": res["answer"],
                        "reports": res["reports"], "sources": sorted(set(tb.sources)),
                        "judge": verdict, "secs": secs, "tokens": p + comp})
            print(f"{cid} {arm:6} {'PASS' if verdict['passed'] else 'FAIL'} {secs:6.1f}s {p + comp:5d} tok  "
                  f"{verdict['why']}", flush=True)
    json.dump({"raw": raw, "handoffs": log.rows}, open(OUT / "results_raw.json", "w", encoding="utf-8"), indent=1)
    write_outputs(cases, rows, log)


def write_outputs(cases, rows, log):
    stat = {}
    for arm in ("single", "multi"):
        r = rows[arm]
        lat = [x["secs"] for x in r]
        pt, ct = sum(x["prompt"] for x in r), sum(x["completion"] for x in r)
        stat[arm] = {"pass": sum(x["passed"] for x in r), "n": len(r), "p50": statistics.median(lat),
                     "p99": percentile(lat, 99), "tokens": pt + ct, "prompt": pt, "completion": ct,
                     "cost_q": cost(pt, ct) / len(r)}
    s, m = stat["single"], stat["multi"]
    mult = m["tokens"] / s["tokens"]

    by_hand = defaultdict(int)
    for row in log.rows:
        if row["arm"] == "multi":
            by_hand[row["handoff"]] += row["total"]
    top, top_tok = max(by_hand.items(), key=lambda kv: kv[1])
    share = 100 * top_tok / m["tokens"]
    mult_line = (f"Context re-send multiplier: {mult:.1f}x (multi {m['tokens']} tokens / single {s['tokens']} tokens). "
                 f"Largest share: {top}, {share:.0f}% of all multi-arm tokens.")

    fmt = lambda a: (f"{a['pass']}/{a['n']} ({100 * a['pass'] / a['n']:.0f}%)")
    lines = [
        "# Race table: single agent vs orchestrator + 2 workers", "",
        f"Cases: Week-6 `results/test_cases_week6.json` Q1-Q10, verbatim: "
        + "; ".join(f"Q{c['id']} {c['question']}" for c in cases) + ".", "",
        "| Metric | Single agent | Multi (orchestrator + 2 workers) |", "|---|---|---|",
        f"| Pass rate (same judge) | {fmt(s)} | {fmt(m)} |",
        f"| Latency p50 | {s['p50']:.1f} s | {m['p50']:.1f} s |",
        f"| Latency p99 (linear interp., n=10, so about the max) | {s['p99']:.1f} s | {m['p99']:.1f} s |",
        f"| Total tokens (prompt + completion) | {s['tokens']} ({s['prompt']} + {s['completion']}) | "
        f"{m['tokens']} ({m['prompt']} + {m['completion']}) |",
        f"| Cost per question (reference ${PRICE_IN:.2f} in / ${PRICE_OUT:.2f} out per 1M tokens) | "
        f"${s['cost_q']:.6f} | ${m['cost_q']:.6f} |", "",
        f"**{mult_line}**", "",
        "Per-case detail:", "", "| Case | Single | s | tok | Multi | s | tok |", "|---|---|---|---|---|---|---|",
    ]
    for a, b in zip(rows["single"], rows["multi"]):
        lines.append(f"| {a['case']} | {'PASS' if a['passed'] else 'FAIL'} | {a['secs']:.1f} | "
                     f"{a['prompt'] + a['completion']} | {'PASS' if b['passed'] else 'FAIL'} | {b['secs']:.1f} | "
                     f"{b['prompt'] + b['completion']} |")
    lines += ["", "Method notes (read before trusting the numbers):",
              "- One pass per arm. No re-runs. Prompts frozen before the run. Arm order alternated per case.",
              "- Model: local Ollama llama3.2 (3B). Tokens are Ollama's own prompt_eval_count + eval_count. "
              f"Real cost is $0; the dollar figure applies a hosted reference price (assumption, adjustable in week10_race.py).",
              "- Judge: Week 6 labels as rules (generation cases must refuse; retrieval cases must retrieve the "
              "expected PDF and not refuse) plus an LLM groundedness/answers check by the same llama3.2. Judge tokens "
              "are excluded from both arms. A 3B self-judge is noisy; see results_raw.json to audit every verdict.",
              "- Retriever: BM25 over the persisted Chroma chunks (src/chunk_search.py), same for both arms, because the "
              "project venv is dead on this machine. Absolute pass rate is below the Week 5 dense retriever.",
              "- Eligibility depends on the retrieved policy, so the orchestrator runs workers sequentially; this task "
              "does not parallelise."]
    (OUT / "race_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    log_lines = ["# handoffs.log  (one row per LLM call; a hand-off is who sent context to whom)",
                 "# columns: case | arm | hand-off | turn | prompt_tokens | completion_tokens | total | secs"]
    for r in log.rows:
        log_lines.append(f"{r['case']} | {r['arm']} | {r['handoff']} | turn {r['turn']} | {r['prompt']} | "
                         f"{r['completion']} | {r['total']} | {r['secs']}")
    for arm in ("single", "multi"):
        log_lines += ["", f"# TOTAL by hand-off, arm={arm}"]
        agg = defaultdict(int)
        for r in log.rows:
            if r["arm"] == arm:
                agg[r["handoff"]] += r["total"]
        tot = sum(agg.values())
        for h, t in sorted(agg.items(), key=lambda kv: -kv[1]):
            log_lines.append(f"{h}: {t} tokens ({100 * t / tot:.0f}% of {arm} total {tot})")
    log_lines += ["", mult_line]
    (OUT / "handoffs.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n" + mult_line)


def failure():
    OUT.mkdir(exist_ok=True)
    cases = json.load(open(CASES_FILE, encoding="utf-8"))
    c = next(x for x in cases if x["id"] == FAILURE_CASE_ID)
    llm = Meter()
    llm.chat_usage([{"role": "user", "content": "hi"}])
    report = {}
    for arm in ("multi", "single"):
        log = HandoffLog()
        res, tb, secs = run_arm(llm, log, arm, f"Q{c['id']}-500", c["question"], inject="search_policy_docs")
        evidence = " ".join(tb.context)
        ans_nums = set(re.findall(r"\d+(?:\.\d+)?", res["answer"]))
        unsupported = sorted(n for n in ans_nums if n not in evidence)   # numbers no tool ever returned
        report[arm] = {"answer": res["answer"], "reports": res["reports"], "tool_errors": res["tool_errors"],
                       "search_calls": [x for x in tb.calls if x["tool"] == "search_policy_docs"],
                       "tokens": log.total(arm), "secs": secs, "numbers_not_from_any_tool": unsupported,
                       "refused": is_refusal(res["answer"])}
        print(f"\n== {arm}: {json.dumps(report[arm], indent=1)}")
    json.dump({"case": c, **report}, open(OUT / "failure_raw.json", "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        smoke(sys.argv[sys.argv.index("--smoke") + 1])
    elif "--failure" in sys.argv:
        failure()
    else:
        race()
