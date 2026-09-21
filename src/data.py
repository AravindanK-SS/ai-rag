EMPLOYEE_DB = {
    "EMP001": {"name": "Alice Smith", "tenure_years": 1, "location": "CA"},
    "EMP002": {"name": "Bob Jones", "tenure_years": 3, "location": "NY"},
    "EMP003": {"name": "Charlie Brown", "tenure_years": 5, "location": "TX"},
    "EMP004": {"name": "Diana Prince", "tenure_years": 0, "location": "UK"},
    "EMP005": {"name": "Eve Davis", "tenure_years": 2, "location": "EU"},
    "EMP006": {"name": "Frank Miller", "tenure_years": 10, "location": "CA"},
    "EMP007": {"name": "Grace Hopper", "tenure_years": 4, "location": "NY"},
    "EMP008": {"name": "Hank Pym", "tenure_years": 1, "location": "TX"},
    "EMP009": {"name": "Ivy Poison", "tenure_years": 6, "location": "UK"},
    "EMP010": {"name": "Jack Sparrow", "tenure_years": 0, "location": "EU"}
}

# The ground truth answers for the 10 questions
QUESTIONS = [
    {"id": 1, "emp_id": "EMP001", "q": "What is the leave balance for EMP001?", "expected_answer": 10.0},
    {"id": 2, "emp_id": "EMP002", "q": "What is the leave balance for EMP002?", "expected_answer": 45.0},
    {"id": 3, "emp_id": "EMP003", "q": "What is the leave balance for EMP003?", "expected_answer": 50.0},
    {"id": 4, "emp_id": "EMP004", "q": "What is the leave balance for EMP004?", "expected_answer": 0.0},
    {"id": 5, "emp_id": "EMP005", "q": "What is the leave balance for EMP005?", "expected_answer": 40.0},
    {"id": 6, "emp_id": "EMP006", "q": "What is the leave balance for EMP006?", "expected_answer": 120.0},
    {"id": 7, "emp_id": "EMP007", "q": "What is the leave balance for EMP007?", "expected_answer": 60.0},
    {"id": 8, "emp_id": "EMP008", "q": "What is the leave balance for EMP008?", "expected_answer": 10.0},
    {"id": 9, "emp_id": "EMP009", "q": "What is the leave balance for EMP009?", "expected_answer": 120.0},
    {"id": 10, "emp_id": "EMP010", "q": "What is the leave balance for EMP010?", "expected_answer": 0.0}
]
