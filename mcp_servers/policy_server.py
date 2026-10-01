#!/usr/bin/env python3
"""
Policy Search MCP Server (Server 1)
Implements Model Context Protocol (MCP) JSON-RPC 2.0 over stdio.
Exposes HR policy search and summary capabilities.
"""
import sys
import json
import logging

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

SERVER_INFO = {
    "name": "policy-search-server",
    "version": "1.0.0"
}

EARLIEST_EFFECTIVE_DATE = "2024-04-01"
# The handbook is context the app attaches (a resource), not something the model must fetch via a tool.
HANDBOOK_URI = "policy://handbook/current"

POLICIES = {
    "annual leave": "Annual Leave Policy (Effective 2024-04-01): Full-time employees accrue 1.5 days per month up to 18 days per year. Unused leave up to 5 days can carry forward.",
    "sick leave": "Sick Leave Policy (Effective 2024-04-01): Employees receive 10 paid sick days per year. Medical certificate required for absences exceeding 2 consecutive days.",
    "core hours": "Core Hours Policy (Effective 2024-04-01): Core working hours are 10:00 AM to 4:00 PM local time. Flexible arrival permitted between 8:00 AM and 10:00 AM.",
    "attendance": "Attendance Policy (Effective 2024-04-01): Regular attendance is required. Unplanned absences must be reported to the line manager by 09:00 AM."
}

def get_tools_definition(legacy_docstring: bool = False):
    if legacy_docstring:
        desc = "Search policy documents."
    else:
        desc = (
            "Search company HR policy documents by topic and effective date. "
            "Input 'query' with the topic (e.g., 'annual leave', 'attendance') "
            "and 'effective_date' in YYYY-MM-DD format. Note: Earliest active policy "
            "version is 2024-04-01; queries prior to this date will return date bounds for recovery."
        )

    return [
        {
            "name": "search_policy",
            "description": desc,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic or policy name to search for (e.g., 'annual leave', 'core hours')."
                    },
                    "effective_date": {
                        "type": "string",
                        "description": "Policy version effective date in YYYY-MM-DD format (earliest is 2024-04-01).",
                        "default": "2024-04-01"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_policy_summary",
            "description": "Retrieve an executive summary of key guidelines for a high-level policy area.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "High-level topic area (e.g., 'leave', 'conduct', 'remote_work')."
                    }
                },
                "required": ["topic"]
            }
        }
    ]

def handle_search_policy(args: dict, legacy_error: bool = False):
    query = args.get("query", "").lower()
    effective_date = args.get("effective_date", "2024-04-01")

    # Date version check
    if effective_date < EARLIEST_EFFECTIVE_DATE:
        if legacy_error:
            return {
                "content": [{"type": "text", "text": "Error 3: Policy not found"}],
                "isError": True
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": (
                        f"Recoverable Error: No policy version effective {effective_date}: "
                        f"earliest available is {EARLIEST_EFFECTIVE_DATE}. "
                        f"Please re-query using effective_date='{EARLIEST_EFFECTIVE_DATE}' or later."
                    )
                }],
                "isError": True
            }

    # Match policy
    for key, text in POLICIES.items():
        if key in query or any(w in text.lower() for w in query.split()):
            return {
                "content": [{"type": "text", "text": text}],
                "isError": False
            }

    return {
        "content": [{
            "type": "text",
            "text": f"No policy matching '{query}' found for effective date {effective_date}. Available topics: {', '.join(POLICIES.keys())}."
        }],
        "isError": False
    }

def handle_get_policy_summary(args: dict):
    topic = args.get("topic", "").lower()
    summary = f"Summary for {topic}: All operations adhere to standard corporate governance effective {EARLIEST_EFFECTIVE_DATE}."
    return {
        "content": [{"type": "text", "text": summary}],
        "isError": False
    }

def process_message(msg: dict, legacy_mode: bool = False) -> dict:
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    },
                    "resources": {}
                },
                "serverInfo": SERVER_INFO
            }
        }

    elif method == "notifications/initialized":
        return None

    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"resources": [{
                "uri": HANDBOOK_URI,
                "name": "HR Handbook (current policy versions)",
                "mimeType": "text/plain"
            }]}
        }

    elif method == "resources/read":
        uri = msg.get("params", {}).get("uri")
        if uri != HANDBOOK_URI:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32002, "message": f"Resource not found: {uri}"}}
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"contents": [{
                "uri": HANDBOOK_URI,
                "mimeType": "text/plain",
                "text": "\n".join(POLICIES.values())
            }]}
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": get_tools_definition(legacy_docstring=legacy_mode)
            }
        }

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "search_policy":
            result = handle_search_policy(tool_args, legacy_error=legacy_mode)
        elif tool_name == "get_policy_summary":
            result = handle_get_policy_summary(tool_args)
        else:
            result = {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True
            }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result
        }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

def main():
    legacy_mode = "--legacy" in sys.argv
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = process_message(req, legacy_mode=legacy_mode)
            if res is not None:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
