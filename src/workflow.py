import re
import time
from src.tools import get_employee_record, get_jurisdiction_rules, compute_leave_balance, Jurisdiction
from src.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

class FixedWorkflow:
    def __init__(self):
        self.llm = get_llm()
        self.total_tokens_used = 0
        self.total_cost = 0.0
        
    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)
        
    def _simulate_cost(self, tokens: int) -> float:
        return (tokens / 1000.0) * 0.01

    def run(self, user_input: str) -> str:
        # Step 1: Extract Employee ID
        emp_id_match = re.search(r'EMP\d{3}', user_input)
        if not emp_id_match:
            return "Could not identify Employee ID in the question."
            
        emp_id = emp_id_match.group(0)
        
        # Step 2: Get Employee Record
        emp_record = get_employee_record(emp_id)
        if "Employee not found" in emp_record:
            return "Employee not found."
            
        # Parse tenure and jurisdiction from record
        # Format: "Name: Alice Smith, Tenure: 1 years, Jurisdiction: CA"
        tenure_match = re.search(r'Tenure:\s*(\d+)', emp_record)
        jur_match = re.search(r'Jurisdiction:\s*([A-Z]{2})', emp_record)
        
        if not tenure_match or not jur_match:
            return "Failed to parse employee record."
            
        tenure = int(tenure_match.group(1))
        jurisdiction = jur_match.group(1)
        
        # Step 3: Get Jurisdiction Rules
        rules = get_jurisdiction_rules(jurisdiction)
        
        # Step 4: Extract base multiplier from rules
        # Format: "Base multiplier is 10. If tenure < 2..."
        mult_match = re.search(r'Base multiplier is (\d+)', rules)
        if not mult_match:
            return "Failed to parse rules."
            
        multiplier = float(mult_match.group(1))
        
        # Step 5: Compute Leave Balance
        balance_res = compute_leave_balance(tenure, multiplier)
        
        # Step 6: Use LLM to format the final answer
        prompt = f"""
You are an HR Assistant.
Question: {user_input}

Employee Record: {emp_record}
Jurisdiction Rules: {rules}
Computed Balance: {balance_res}

Answer the question clearly using the provided data.
"""
        self.total_tokens_used += self._estimate_tokens(prompt)
        self.total_cost += self._simulate_cost(self._estimate_tokens(prompt))
        
        from langfuse.langchain import CallbackHandler
        langfuse_handler = CallbackHandler()
        response = self.llm.invoke(prompt, config={"callbacks": [langfuse_handler]})
        
        output_tokens = self._estimate_tokens(response.content)
        self.total_tokens_used += output_tokens
        self.total_cost += self._simulate_cost(output_tokens)
        
        return response.content
