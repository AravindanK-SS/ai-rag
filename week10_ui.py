"""Backend helpers for the Week 10 UI page (week10.html): saved race results and a live side-by-side run."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.w10_agents import HandoffLog, Meter
from week10_race import PRICE_IN, PRICE_OUT, cost, percentile, run_arm

OUT = Path("week10")
_llm = None


def _read(name):
    p = OUT / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def saved_results():
    """Summarises the official race (week10/results_raw.json) exactly as race_table.md does."""
    p = OUT / "results_raw.json"
    if not p.exists():
        return {"available": False}
    d = json.load(open(p, encoding="utf-8"))
    arms = {}
    for arm in ("single", "multi"):
        rs = [r for r in d["raw"] if r["arm"] == arm]
        hs = [h for h in d["handoffs"] if h["arm"] == arm]
        pt, ct = sum(h["prompt"] for h in hs), sum(h["completion"] for h in hs)
        lat = [r["secs"] for r in rs]
        by = defaultdict(int)
        for h in hs:
            by[h["handoff"]] += h["total"]
        arms[arm] = {"pass": sum(r["judge"]["passed"] for r in rs), "n": len(rs),
                     "p50": statistics.median(lat), "p99": percentile(lat, 99),
                     "tokens": pt + ct, "cost_q": cost(pt, ct) / len(rs),
                     "handoffs": sorted(by.items(), key=lambda kv: -kv[1])}
    cases = {}
    for r in d["raw"]:
        cases.setdefault(r["case"], {"question": r["question"]})[r["arm"]] = {
            "passed": r["judge"]["passed"], "why": r["judge"]["why"], "secs": r["secs"],
            "tokens": r["tokens"], "answer": r["answer"]}
    failure = json.load(open(OUT / "failure_raw.json", encoding="utf-8")) if (OUT / "failure_raw.json").exists() else None
    return {"available": True, "arms": arms, "multiplier": arms["multi"]["tokens"] / arms["single"]["tokens"],
            "cases": cases, "failure": failure, "verdict": _read("verdict.md"),
            "price": {"in": PRICE_IN, "out": PRICE_OUT}}


def live_compare(question, inject500=False):
    global _llm
    if not question.strip():
        raise ValueError("empty question")
    if _llm is None:
        _llm = Meter()
    out = {}
    for arm in ("single", "multi"):
        log = HandoffLog()
        res, tb, secs = run_arm(_llm, log, arm, "live", question,
                                inject="search_policy_docs" if inject500 else None)
        p, c = log.split(arm, "live")
        out[arm] = {"answer": res["answer"], "secs": secs, "tokens": p + c, "prompt": p, "completion": c,
                    "cost": cost(p, c), "handoffs": log.rows, "reports": res["reports"],
                    "tool_errors": res["tool_errors"], "tool_calls": tb.calls}
    return out
