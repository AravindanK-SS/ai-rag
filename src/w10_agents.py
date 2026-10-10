"""
Week 10: single agent vs orchestrator + two workers, metered per LLM call.

Every LLM call is a "hand-off" row (who sent the context, who received it, real Ollama token counts),
so the re-send cost of the multi-agent pattern can be read straight from handoffs.log.

Prompts below are FROZEN before the official race. They are not tuned between runs.
"""
import json
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from src.ollama_chat import OllamaChat, OllamaUnavailable
from src.w10_tools import Toolbox, ToolError

REFUSAL = "I cannot answer this because the uploaded documents do not contain the required information."

SINGLE_SYSTEM = (
    "You are an HR Policy Assistant. Use search_policy_docs to find policy text; use the HRIS tools only "
    "when the user gives an employee ID. Answer ONLY from tool results. Be concise. "
    f"If the tool results do not contain the answer, reply exactly: '{REFUSAL}'"
)
DECOMPOSE_SYSTEM = (
    "You are the orchestrator of an HR policy team. Split the employee question into sub-tasks. "
    'Reply with JSON only: {"policy_query": "<short keyword query for the policy search>", '
    '"needs_eligibility": <true only if the question asks whether a specific employee qualifies, '
    'or needs their HRIS data>, "employee_id": "<EMPnnn from the question, else null>"}'
)
POLICY_WORKER_SYSTEM = (
    "You are the policy-retrieval worker. Call search_policy_docs once with a focused query, then report "
    "the relevant policy facts in at most 5 short bullets, each tagged with its source file. If the "
    "passages are not relevant, reply exactly: NO RELEVANT POLICY FOUND. Never answer from memory."
)
ELIGIBILITY_WORKER_SYSTEM = (
    "You are the eligibility-calculation worker. You get a question and the policy findings. State who is "
    "eligible and under what conditions. If an employee ID is given, check HRIS with your tools. "
    "Never invent employee data. Reply in at most 4 short sentences."
)
SYNTH_SYSTEM = (
    "You are the orchestrator writing the final answer for an employee. Use ONLY the worker reports "
    f"below. Be concise. If the reports do not contain the answer, reply exactly: '{REFUSAL}'"
)


class Meter(OllamaChat):
    """OllamaChat plus real token usage and optional JSON mode."""

    def chat_usage(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
                   fmt: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        payload: Dict[str, Any] = {"model": self.model, "messages": messages, "stream": False,
                                   "options": {"temperature": 0}}
        if tools:
            payload["tools"] = tools
        if fmt:
            payload["format"] = fmt
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise OllamaUnavailable(f"Ollama chat failed: {e}") from e
        usage = {"prompt": body.get("prompt_eval_count", 0), "completion": body.get("eval_count", 0),
                 "secs": round(time.time() - t0, 2)}
        return body.get("message", {}), usage


class HandoffLog:
    def __init__(self):
        self.rows: List[Dict[str, Any]] = []

    def add(self, case: str, arm: str, handoff: str, turn: int, usage: Dict[str, Any]):
        self.rows.append({"case": case, "arm": arm, "handoff": handoff, "turn": turn,
                          "prompt": usage["prompt"], "completion": usage["completion"],
                          "total": usage["prompt"] + usage["completion"], "secs": usage["secs"]})

    def total(self, arm: str, case: Optional[str] = None) -> int:
        return sum(r["total"] for r in self.rows if r["arm"] == arm and (case is None or r["case"] == case))

    def split(self, arm: str, case: str) -> Tuple[int, int]:
        rs = [r for r in self.rows if r["arm"] == arm and r["case"] == case]
        return sum(r["prompt"] for r in rs), sum(r["completion"] for r in rs)


def tool_loop(llm: Meter, log: HandoffLog, tb: Toolbox, case: str, arm: str, handoff: str,
              system: str, user: str, tool_names: List[str], max_turns: int = 4) -> Dict[str, Any]:
    """Generic tool-calling loop. Tool errors go back to the model as the tool message (Week 9 behaviour)."""
    tools = tb.schemas(*tool_names)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    out = {"text": "", "tool_errors": [], "tool_calls": 0}
    for turn in range(1, max_turns + 1):
        msg, usage = llm.chat_usage(messages, tools)
        log.add(case, arm, handoff, turn, usage)
        calls = msg.get("tool_calls") or []
        if not calls:
            out["text"] = (msg.get("content") or "").strip()
            return out
        messages.append(msg)
        for call in calls:
            fn = call.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            out["tool_calls"] += 1
            try:
                result = tb.call(fn.get("name", ""), args)
            except ToolError as e:
                result = f"ERROR: {e}"
                out["tool_errors"].append(str(e))
            messages.append({"role": "tool", "tool_name": fn.get("name", ""), "content": result})
    out["text"] = out["text"] or "(step limit reached without a final message)"
    return out


def run_single(llm: Meter, log: HandoffLog, tb: Toolbox, case: str, question: str) -> Dict[str, Any]:
    r = tool_loop(llm, log, tb, case, "single", "user -> single_agent", SINGLE_SYSTEM, question,
                  ["search_policy_docs", "get_employee_grade_band", "get_accrued_leave_balance"])
    return {"answer": r["text"], "tool_errors": r["tool_errors"], "reports": {}}


def run_multi(llm: Meter, log: HandoffLog, tb: Toolbox, case: str, question: str) -> Dict[str, Any]:
    # 1) decompose
    msg, usage = llm.chat_usage([{"role": "system", "content": DECOMPOSE_SYSTEM},
                                 {"role": "user", "content": question}], fmt="json")
    log.add(case, "multi", "user -> orchestrator (decompose)", 1, usage)
    try:
        plan = json.loads(msg.get("content") or "{}")
    except json.JSONDecodeError:
        plan = {}
    policy_query = plan.get("policy_query") or question
    emp_id = plan.get("employee_id") if isinstance(plan.get("employee_id"), str) else None
    needs_elig = bool(plan.get("needs_eligibility"))

    # 2) policy worker
    pol = tool_loop(llm, log, tb, case, "multi", "orchestrator -> policy_worker", POLICY_WORKER_SYSTEM,
                    f"Find policy text relevant to: {policy_query}\nOriginal question: {question}",
                    ["search_policy_docs"], max_turns=3)
    reports = {"plan": plan, "policy_worker": pol["text"]}

    # 3) eligibility worker: depends on the policy findings, so it cannot run in parallel with step 2
    elig_text = "(not requested)"
    if needs_elig:
        el = tool_loop(llm, log, tb, case, "multi", "orchestrator -> eligibility_worker",
                       ELIGIBILITY_WORKER_SYSTEM,
                       f"Question: {question}\nEmployee ID: {emp_id}\nPolicy findings:\n{pol['text']}",
                       ["get_employee_grade_band", "get_accrued_leave_balance"], max_turns=3)
        elig_text = el["text"]
        pol["tool_errors"] += el["tool_errors"]
    reports["eligibility_worker"] = elig_text

    # 4) synthesise
    msg, usage = llm.chat_usage([
        {"role": "system", "content": SYNTH_SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nPolicy worker report:\n{pol['text']}\n\n"
                                    f"Eligibility worker report:\n{elig_text}"}])
    log.add(case, "multi", "workers -> orchestrator (synthesis)", 1, usage)
    return {"answer": (msg.get("content") or "").strip(), "tool_errors": pol["tool_errors"],
            "reports": reports, "policy_tool_calls": pol["tool_calls"]}
