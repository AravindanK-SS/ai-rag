from enum import Enum
from typing import Dict, Any, Union
from src.data import EMPLOYEE_DB

class Jurisdiction(str, Enum):
    CA = "CA"
    NY = "NY"
    TX = "TX"
    UK = "UK"
    EU = "EU"

def get_employee_record(emp_id: str) -> str:
    """
    Look up an employee's basic record by their employee ID.
    Returns the employee name, tenure in years, and their jurisdiction location.
    
    Args:
        emp_id: The employee ID (e.g., EMP001).
    """
    record = EMPLOYEE_DB.get(emp_id)
    if record:
        return f"Name: {record['name']}, Tenure: {record['tenure_years']} years, Jurisdiction: {record['location']}"
    return "Employee not found."

def get_jurisdiction_rules(jurisdiction: str) -> str:
    """
    Look up the specific HR rules and leave multipliers for a given jurisdiction.
    This does NOT look up employee records, only the general rules for a location.
    
    Args:
        jurisdiction: The jurisdiction code (must be one of: CA, NY, TX, UK, EU).
    """
    try:
        # Validate using Enum
        valid_jurisdiction = Jurisdiction(jurisdiction)
    except ValueError:
        return f"Invalid jurisdiction: {jurisdiction}. Must be one of {[j.value for j in Jurisdiction]}"

    rules = {
        Jurisdiction.CA: "Base multiplier is 10. If tenure < 2 years, notice period rule is 2 weeks. Otherwise 4 weeks.",
        Jurisdiction.NY: "Base multiplier is 15. If tenure < 2 years, notice period rule is 2 weeks. Otherwise 4 weeks.",
        Jurisdiction.TX: "Base multiplier is 10. Notice period is at-will (0 weeks).",
        Jurisdiction.UK: "Base multiplier is 20. If tenure < 2 years, notice period rule is 4 weeks. Otherwise 8 weeks.",
        Jurisdiction.EU: "Base multiplier is 20. If tenure < 2 years, notice period rule is 4 weeks. Otherwise 12 weeks."
    }
    return rules.get(valid_jurisdiction, "Rules not found.")

def compute_leave_balance(tenure_years: int, rule_multiplier: float) -> str:
    """
    Computes the total numeric leave balance by multiplying the employee's tenure by the jurisdiction's rule multiplier.
    
    Args:
        tenure_years: The number of years the employee has worked.
        rule_multiplier: The base multiplier for the jurisdiction.
    """
    balance = float(tenure_years) * float(rule_multiplier)
    return f"Calculated leave balance: {balance}"

# Langchain tool wrappers
from langchain_core.tools import tool

@tool
def tool_get_employee_record(emp_id: str) -> str:
    """
    Look up an employee's basic record by their employee ID.
    Returns the employee name, tenure in years, and their jurisdiction location.
    """
    return get_employee_record(emp_id)

@tool
def tool_get_jurisdiction_rules(jurisdiction: str) -> str:
    """
    Look up the specific HR rules and leave multipliers for a given jurisdiction.
    This does NOT look up employee records, only the general rules for a location.
    Valid jurisdictions are: CA, NY, TX, UK, EU.
    """
    return get_jurisdiction_rules(jurisdiction)

@tool
def tool_compute_leave_balance(tenure_years: int, rule_multiplier: float) -> str:
    """
    Computes the total numeric leave balance by multiplying the employee's tenure by the jurisdiction's rule multiplier.
    """
    return compute_leave_balance(tenure_years, rule_multiplier)

TOOLS = [tool_get_employee_record, tool_get_jurisdiction_rules, tool_compute_leave_balance]
