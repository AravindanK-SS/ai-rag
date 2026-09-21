import time
import csv
import statistics
import traceback
from src.agent import HRAgent, BudgetExceededException
from src.workflow import FixedWorkflow
from src.data import QUESTIONS
import os
from dotenv import load_dotenv
load_dotenv()

def check_pass(expected, response_text):
    # simple check if expected float is in text
    # expected is a float like 10.0, 120.0
    return str(int(expected)) in response_text or str(expected) in response_text

def run_race():
    results = []
    
    agent_latencies = []
    agent_tokens = 0
    agent_cost = 0.0
    agent_passes = 0
    
    wf_latencies = []
    wf_tokens = 0
    wf_cost = 0.0
    wf_passes = 0
    
    print("--- RACING AGENT VS WORKFLOW ---")
    for q in QUESTIONS:
        print(f"\nProcessing Q{q['id']}: {q['q']}")
        expected = q['expected_answer']
        
        # Test Agent
        agent = HRAgent()
        t0 = time.time()
        try:
            agent_response = agent.run(q['q'])
            latency = time.time() - t0
            agent_latencies.append(latency)
            agent_tokens += agent.total_tokens_used
            agent_cost += agent.total_cost
            if check_pass(expected, agent_response):
                agent_passes += 1
                print(f"  Agent PASSED ({latency:.2f}s)")
            else:
                print(f"  Agent FAILED: Output -> {agent_response}")
        except Exception as e:
            print(f"  Agent ERRORED: {e}")
            
        # Test Workflow
        wf = FixedWorkflow()
        t0 = time.time()
        try:
            wf_response = wf.run(q['q'])
            latency = time.time() - t0
            wf_latencies.append(latency)
            wf_tokens += wf.total_tokens_used
            wf_cost += wf.total_cost
            if check_pass(expected, wf_response):
                wf_passes += 1
                print(f"  Workflow PASSED ({latency:.2f}s)")
            else:
                print(f"  Workflow FAILED: Output -> {wf_response}")
        except Exception as e:
            print(f"  Workflow ERRORED: {e}")

    # Calculate metrics
    metrics = {
        "Agent": {
            "Pass Rate (%)": (agent_passes / len(QUESTIONS)) * 100,
            "p50 Latency (s)": statistics.median(agent_latencies) if agent_latencies else 0.0,
            "Total Tokens": agent_tokens,
            "Cost/Task ($)": agent_cost / len(QUESTIONS)
        },
        "Workflow": {
            "Pass Rate (%)": (wf_passes / len(QUESTIONS)) * 100,
            "p50 Latency (s)": statistics.median(wf_latencies) if wf_latencies else 0.0,
            "Total Tokens": wf_tokens,
            "Cost/Task ($)": wf_cost / len(QUESTIONS)
        }
    }
    
    os.makedirs("results", exist_ok=True)
    with open("results/race.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["System", "Pass Rate (%)", "p50 Latency (s)", "Total Tokens", "Cost/Task ($)"])
        for sys_name, data in metrics.items():
            writer.writerow([
                sys_name,
                f"{data['Pass Rate (%)']:.1f}",
                f"{data['p50 Latency (s)']:.2f}",
                data['Total Tokens'],
                f"{data['Cost/Task ($)']:.4f}"
            ])
            
    print("\n--- RESULTS ---")
    for sys_name, data in metrics.items():
        print(f"{sys_name}: Pass: {data['Pass Rate (%)']}%, p50: {data['p50 Latency (s)']:.2f}s, Tokens: {data['Total Tokens']}, Cost/Task: ${data['Cost/Task ($)']:.4f}")

def test_budget_termination():
    print("\n--- TESTING BUDGET TERMINATION ---")
    agent = HRAgent(max_iterations=1) # Forces budget termination
    try:
        agent.run("What is the leave balance for EMP001?")
    except BudgetExceededException as e:
        print(f"Budget termination successful: {e}")
        with open("results/budget_log.txt", "w") as f:
            f.write(f"Triggered by Max Iterations (set to 1).\nException: {traceback.format_exc()}")
            
if __name__ == "__main__":
    run_race()
    test_budget_termination()
