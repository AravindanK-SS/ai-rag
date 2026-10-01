# Error Handling Before & After: Docstring-as-Prompt & Recoverable Errors

Both transcripts below are captured output from `week9_evidence.py` running the SAME failing call
(`effective_date=2023-01-01`) through `src/mcp_agent.py`. Only the server's docstring and error text differ
(`mcp_servers/policy_server.py --legacy` vs default).

## 1. Docstring rewrite (policy_server.py `search_policy`)
- Before: `"Search policy documents."`
- After: `"Search company HR policy documents by topic and effective date. Input 'query' with the topic (e.g., 'annual leave', 'attendance') and 'effective_date' in YYYY-MM-DD format. Note: Earliest active policy version is 2024-04-01; queries prior to this date will return date bounds for recovery."`

## 2. Error path rewrite
- Before: `Error 3: Policy not found`
- After: `Recoverable Error: No policy version effective 2023-01-01: earliest available is 2024-04-01. Please re-query using effective_date='2024-04-01' or later.`

## 3. Transcript BEFORE (legacy docstring + opaque error)
```
[User]: What was our annual leave policy effective 2023-01-01?
[Agent mode]: fallback (LLM unavailable: Ollama chat failed (llama3.2 @ http://localhost:11434): HTTP Error 404: Not Found)
[Action 1]: search_policy {"query": "What was our annual leave policy effective 2023-01-01?", "effective_date": "2023-01-01"}
[Tool result 1] (isError=True): Error 3: Policy not found
[Final answer]: Error 3: Policy not found
```
Steps taken: 1. The opaque code carries no date bound, so the host cannot tell "version does not exist
yet" from "HRIS is down", and it dead-ends.

## 4. Transcript AFTER (docstring-as-prompt + recoverable error)
```
[User]: What was our annual leave policy effective 2023-01-01?
[Agent mode]: fallback (LLM unavailable: Ollama chat failed (llama3.2 @ http://localhost:11434): HTTP Error 404: Not Found)
[Action 1]: search_policy {"query": "What was our annual leave policy effective 2023-01-01?", "effective_date": "2023-01-01"}
[Tool result 1] (isError=True): Recoverable Error: No policy version effective 2023-01-01: earliest available is 2024-04-01. Please re-query using effective_date='2024-04-01' or later.
[Action 2]: search_policy {"query": "What was our annual leave policy effective 2023-01-01?", "effective_date": "2024-04-01"}
[Tool result 2] (isError=False): Annual Leave Policy (Effective 2024-04-01): Full-time employees accrue 1.5 days per month up to 18 days per year. Unused leave up to 5 days can carry forward.
[Final answer]: Recoverable Error: No policy version effective 2023-01-01: earliest available is 2024-04-01. Please re-query using effective_date='2024-04-01' or later. Annual Leave Policy (Effective 2024-04-01): Full-time employees accrue 1.5 days per month up to 18 days per year. Unused leave up to 5 days can carry forward.
```
Steps taken: 2. The error names the earliest valid date, so the second call succeeds and the
answer states that no 2023 version exists.

> Note: the "Agent mode" line shows who drove the recovery. When Ollama has `llama3.2` pulled, re-run
> `python week9_evidence.py <BASE> <SERVER2>` to capture the LLM-driven version of the same exchange.
