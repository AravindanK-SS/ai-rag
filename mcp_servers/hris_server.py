#!/usr/bin/env python3
"""
HRIS MCP Server (Server 2)
Implements Model Context Protocol (MCP) JSON-RPC 2.0 over stdio.
Exposes employee grade band and accrued leave balance by employee id.
Authored by People Ops.
"""
import sys
import json
import logging

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

SERVER_INFO = {
    "name": "people-ops-hris-server",
    "version": "1.0.0"
}

# HRIS Records for Employee Data
HRIS_RECORDS = {
    "EMP001": {"name": "Alice Smith", "grade_band": "L4 - Senior Associate", "accrued_leave_days": 10.0, "tenure_years": 1, "department": "Engineering"},
    "EMP002": {"name": "Bob Jones", "grade_band": "L5 - Lead Specialist", "accrued_leave_days": 45.0, "tenure_years": 3, "department": "Product"},
    "EMP003": {"name": "Charlie Brown", "grade_band": "L6 - Staff Manager", "accrued_leave_days": 50.0, "tenure_years": 5, "department": "Operations"},
    "EMP004": {"name": "Diana Prince", "grade_band": "L3 - Associate", "accrued_leave_days": 0.0, "tenure_years": 0, "department": "Design"},
    "EMP005": {"name": "Eve Davis", "grade_band": "L4 - Senior Associate", "accrued_leave_days": 40.0, "tenure_years": 2, "department": "Engineering"},
    "EMP006": {"name": "Frank Miller", "grade_band": "L7 - Principal Director", "accrued_leave_days": 120.0, "tenure_years": 10, "department": "Executive"},
    "EMP007": {"name": "Grace Hopper", "grade_band": "L5 - Lead Specialist", "accrued_leave_days": 60.0, "tenure_years": 4, "department": "Engineering"},
    "EMP008": {"name": "Hank Pym", "grade_band": "L3 - Associate", "accrued_leave_days": 10.0, "tenure_years": 1, "department": "Research"},
    "EMP009": {"name": "Ivy Poison", "grade_band": "L6 - Staff Specialist", "accrued_leave_days": 120.0, "tenure_years": 6, "department": "Security"},
    "EMP010": {"name": "Jack Sparrow", "grade_band": "L3 - Associate", "accrued_leave_days": 0.0, "tenure_years": 0, "department": "Logistics"}
}

def get_tools_definition():
    return [
        {
            "name": "get_employee_grade_band",
            "description": "Look up an employee's official grade band and organizational level in HRIS using their employee ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "emp_id": {
                        "type": "string",
                        "description": "The unique employee identifier (e.g., 'EMP001')."
                    }
                },
                "required": ["emp_id"]
            }
        },
        {
            "name": "get_accrued_leave_balance",
            "description": "Fetch the verified, real-time accrued leave balance (in days) from HRIS for a specific employee ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "emp_id": {
                        "type": "string",
                        "description": "The unique employee identifier (e.g., 'EMP001')."
                    }
                },
                "required": ["emp_id"]
            }
        }
    ]

def handle_get_grade_band(args: dict):
    emp_id = args.get("emp_id", "").strip().upper()
    emp = HRIS_RECORDS.get(emp_id)
    if not emp:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: Employee '{emp_id}' not found in HRIS records."
            }],
            "isError": True
        }
    return {
        "content": [{
            "type": "text",
            "text": f"Employee {emp_id} ({emp['name']}) is in Grade Band: {emp['grade_band']} (Department: {emp['department']})."
        }],
        "isError": False
    }

def handle_get_leave_balance(args: dict):
    emp_id = args.get("emp_id", "").strip().upper()
    emp = HRIS_RECORDS.get(emp_id)
    if not emp:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: Employee '{emp_id}' not found in HRIS records."
            }],
            "isError": True
        }
    return {
        "content": [{
            "type": "text",
            "text": f"Employee {emp_id} ({emp['name']}) has an accrued leave balance of {emp['accrued_leave_days']} days."
        }],
        "isError": False
    }

def process_message(msg: dict) -> dict:
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
                    }
                },
                "serverInfo": SERVER_INFO
            }
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": get_tools_definition()
            }
        }

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "get_employee_grade_band":
            result = handle_get_grade_band(tool_args)
        elif tool_name == "get_accrued_leave_balance":
            result = handle_get_leave_balance(tool_args)
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
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = process_message(req)
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
