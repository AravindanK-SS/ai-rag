"""
Tool layer shared by BOTH Week 10 arms (single agent and orchestrator workers).
One implementation, one set of schemas: the arms differ only in who is allowed to call what.
"""
from typing import Any, Dict, List, Optional

from mcp_servers import hris_server
from src.chunk_search import ChunkIndex

CHUNK_CHARS = 600   # per-chunk cap: both arms get the same narrow context, not the whole handbook
TOP_K = 3

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "search_policy_docs": {"type": "function", "function": {
        "name": "search_policy_docs",
        "description": "Search the HR policy PDFs. Returns the top matching passages with their source file.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Short keyword query, e.g. 'annual leave'."}},
            "required": ["query"]}}},
    "get_employee_grade_band": {"type": "function", "function": {
        "name": "get_employee_grade_band",
        "description": "Look up an employee's grade band in HRIS by employee ID.",
        "parameters": {"type": "object", "properties": {
            "emp_id": {"type": "string", "description": "Employee ID, e.g. 'EMP001'."}},
            "required": ["emp_id"]}}},
    "get_accrued_leave_balance": {"type": "function", "function": {
        "name": "get_accrued_leave_balance",
        "description": "Fetch an employee's accrued leave balance in days from HRIS by employee ID.",
        "parameters": {"type": "object", "properties": {
            "emp_id": {"type": "string", "description": "Employee ID, e.g. 'EMP001'."}},
            "required": ["emp_id"]}}},
}

_INDEX: Optional[ChunkIndex] = None


def get_index() -> ChunkIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = ChunkIndex()
    return _INDEX


class ToolError(RuntimeError):
    pass


class Toolbox:
    """Per-run tool executor. Records what was retrieved so the judge sees the same evidence."""

    def __init__(self, inject_500_on: Optional[str] = None):
        self.inject_500_on = inject_500_on
        self.sources: List[str] = []
        self.context: List[str] = []
        self.calls: List[Dict[str, Any]] = []

    def schemas(self, *names: str) -> List[Dict[str, Any]]:
        return [SCHEMAS[n] for n in names]

    def call(self, name: str, args: Dict[str, Any]) -> str:
        self.calls.append({"tool": name, "args": args})
        if name == self.inject_500_on:
            raise ToolError("HTTP 500 Internal Server Error: policy retrieval backend failed")
        if name == "search_policy_docs":
            hits = get_index().search(str(args.get("query", "")), k=TOP_K)
            if not hits:
                return "No matching policy passages found."
            out = []
            for h in hits:
                self.sources.append(h["source"])
                snippet = h["text"][:CHUNK_CHARS]
                self.context.append(snippet)
                out.append(f"[{h['source']} p.{h['page']}] {snippet}")
            return "\n\n".join(out)
        if name in ("get_employee_grade_band", "get_accrued_leave_balance"):
            handler = (hris_server.handle_get_grade_band if name == "get_employee_grade_band"
                       else hris_server.handle_get_leave_balance)
            text = handler({"emp_id": str(args.get("emp_id", ""))})["content"][0]["text"]
            self.context.append(text)
            return text
        raise ToolError(f"Unknown tool '{name}'")
