# Dispatch/Core integration verification

Branch: `feature/dispatch-integration`

Scope: Dispatch orchestration, idempotency, downstream HTTP integration, and
final integration/E2E checks. Other service implementations are unchanged.

## Behavior

- Repeating an unfinished request with the same key resumes the saved assignment
  instead of leaving it permanently pending. PostgreSQL transaction advisory
  locks serialize orchestration across connections/workers and release on error
  or disconnect. Lock connections are separate from the checkpoint-write pool.
- Saved `SLOT_RESERVED` and `CONFIRMED` stages skip already completed operations.
  Earlier stages reuse Work Order claim and Workforce reservation idempotency.
- Transport failures, malformed downstream replies, and downstream server errors
  preserve an unfinished request for retry. A definite reservation rejection
  releases the Work Order claim before persisting the rejection; unresolved
  compensation remains retryable.
- Notification `PROCESSING` responses remain pending. Only `SENT` records delivery.
  Delivery keys stay stable across retries, and a saved `SENT` is never downgraded.
- Completed success and rejection responses remain immutable and replay exactly;
  reusing a key with a changed request still returns HTTP 409.

## Recorded checks

Verified on 24 October 2026 with the repository virtual environment, PostgreSQL 16,
MongoDB 7, and all four service implementations.

| Evidence | Result |
| --- | --- |
| `tests.txt`, `results.xml` | 39 tests passed, including 14 database-backed integration cases |
| `end_to_end.txt` | All four service states agree; exact replay, payload conflict, correlation header, and photo upload/list/download passed |
| `challenge_1_concurrency.txt` | 20 simultaneous requests: one HTTP 201, 19 HTTP 409, one reservation |
| `challenge_2_idempotency.txt` | Simultaneous/sequential duplicates share one assignment, reservation, and notification; changed payload rejected |
| `challenge_3a_resilience.txt` | Provider failure preserves a confirmed assignment, manual recovery succeeds, and lost delivery responses do not duplicate notifications |

The integration cases also inject committed-but-lost responses at claim,
reservation, and confirmation; verify checkpoint recovery after a worker error;
check transient 5xx and compensation recovery; exercise bounded HTTP 202 waits;
and verify execution-lock exclusion and release across repository connections.
They use generated PostgreSQL schemas and MongoDB collection names and remove
only those test namespaces. HTTP challenge scripts create synthetic demo records.

## Reproduce

Install `requirements-dev.txt` in the repository virtual environment, then:

```powershell
docker compose up -d --wait
$env:GEOINSPECT_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest --junitxml=evidence/dispatch-integration/results.xml
```

Integration tests run real APIs through in-process HTTP transport and real
databases; no separately listening service processes are needed for pytest.
Without `GEOINSPECT_INTEGRATION=1`, the 14 database cases are skipped.

For actual HTTP E2E/challenge checks, start `scripts/run_all.py` in another
terminal and run:

```powershell
.\.venv\Scripts\python.exe scripts/end_to_end.py
.\.venv\Scripts\python.exe scripts/challenge_1_concurrency.py
.\.venv\Scripts\python.exe scripts/challenge_2_idempotency.py
.\.venv\Scripts\python.exe scripts/challenge_3a_resilience.py
```

The recorded HTTP run used ports 18101–18104, with the corresponding
`WORK_ORDER_PORT`, `WORKFORCE_PORT`, `DISPATCH_PORT`, `NOTIFICATION_PORT` and
`*_URL` variables set in both terminals. Standard ports work with the defaults.

Recovery of an unfinished assignment is triggered by repeating its original
POST with the same `Idempotency-Key`; there is no background recovery worker.
The test output contains upstream Python 3.14 deprecation warnings; all checks
completed successfully.
