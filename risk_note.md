Author: Written by the internal People Ops engineering team (mcp_servers/hris_server.py); no third-party package is installed, but it still runs inside the agent's trust boundary.
Reach: Reads HRIS records by employee id (name, department, grade band, accrued leave); it has no write tools, no network calls and no file access, and the demo data is a static dict.
Logs: The server itself logs nothing about requests (stderr is errors only); the gateway audit.log records timestamp, caller, tool and employee id, never the returned values.
Stolen token: An unscoped token could enumerate every employee's grade band and leave balance by guessing ids, so grade-band access is denied to the leave-only token at the gateway.
Decision: SHIP behind the gateway with the leave-only scoped token, add rate limits and id-enumeration alerts before the appraisal window, and re-review before any write tool is added.
