# GeoInspect

GeoInspect is an API-only GIS field-inspection dispatch application for Scalable Services (SEZG583), Assignment 1. A work order has a map location, required skill, and fixed time slot. Dispatch assigns a selected inspector only when their rectangular service area covers the point, they possess the skill, and their slot is free.

The implementation demonstrates database-per-service, a transaction spanning Work Order, Workforce, Dispatch, and Notification, concurrency-safe booking, simultaneous idempotency, and retries against a failing mock provider. Inspection photos are stored in MongoDB GridFS without embedding base64 data in work-order documents.

## Services and ports

| Service | Port | Database | Responsibility |
|---|---:|---|---|
| Work Order | 8001 | MongoDB `work_order_db` | Work-order state, location, and GridFS inspection photos |
| Workforce | 8002 | PostgreSQL `workforce_db` | Inspector skills, service areas, and atomic slot reservations |
| Dispatch | 8003 | PostgreSQL `dispatch_db` | Assignment orchestration, idempotency keys, and stored responses |
| Notification | 8004 | MongoDB `notification_db` | Deduplicated mock delivery and failure simulation |

Each database has its own credentials. A service never reads another service's database.
PostgreSQL is exposed on host port `55432` to avoid common conflicts with an existing local server; MongoDB uses `27017`.

## Prerequisites

- Python 3.11 through 3.14
- Docker Desktop with Docker Compose
- PowerShell 7 on Windows for the helper start/stop scripts

## Run from a fresh clone

```powershell
git clone https://github.com/sharmaark/SS_Assignment.git
cd SS_Assignment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
docker compose up -d
docker compose ps
python scripts\run_all.py
```

Wait a few seconds, then verify all processes:

```powershell
Invoke-RestMethod http://localhost:8001/health
Invoke-RestMethod http://localhost:8002/health
Invoke-RestMethod http://localhost:8003/health
Invoke-RestMethod http://localhost:8004/health
```

Keep that terminal open. Swagger UI is available at `http://localhost:<port>/docs`; the terminal receives structured JSON logs with propagated correlation IDs. Press Ctrl+C to stop all four services, then use `docker compose down` to stop databases. Windows users may alternatively use `scripts/start_services.ps1` and `scripts/stop_services.ps1` for background processes and `.run/` log files.

If ports 8001–8004 are already occupied, set a complete override before `run_all.py` and before running the client scripts:

```powershell
$env:WORK_ORDER_PORT="8101"
$env:WORKFORCE_PORT="8102"
$env:DISPATCH_PORT="8103"
$env:NOTIFICATION_PORT="8104"
$env:WORK_ORDER_URL="http://127.0.0.1:8101"
$env:WORKFORCE_URL="http://127.0.0.1:8102"
$env:DISPATCH_URL="http://127.0.0.1:8103"
$env:NOTIFICATION_URL="http://127.0.0.1:8104"
python scripts\run_all.py
```

The initialization scripts run only for a new Docker volume. To deliberately erase all local assignment data and recreate credentials, stop services and run `docker compose down -v`, followed by `docker compose up -d`.

## Configuration

The supplied defaults work with `docker-compose.yml`. Each service has a `.env.example` listing its variables.

| Variable | Used by | Purpose |
|---|---|---|
| `WORKFORCE_DATABASE_URL`, `DISPATCH_DATABASE_URL` | Workforce, Dispatch | Service-owned PostgreSQL connections |
| `WORK_ORDER_MONGODB_URL`, `NOTIFICATION_MONGODB_URL` | Work Order, Notification | Service-owned MongoDB connections |
| `WORK_ORDER_PORT`, `WORKFORCE_PORT`, `DISPATCH_PORT`, `NOTIFICATION_PORT` | Local runner | Service listen ports |
| `WORK_ORDER_URL`, `WORKFORCE_URL`, `NOTIFICATION_URL` | Dispatch | REST dependency addresses |
| `DOWNSTREAM_TIMEOUT_SECONDS` | Dispatch | Per-attempt timeout |
| `NOTIFICATION_MAX_ATTEMPTS`, `RETRY_BASE_SECONDS` | Dispatch | Retry count and exponential-backoff base |
| `IDEMPOTENCY_WAIT_SECONDS` | Dispatch | Bounded wait for a simultaneous duplicate |
| `MAX_PHOTO_BYTES` | Work Order | Per-photo upload limit; default 10 MB |
| `MOCK_MODE`, `MOCK_DELAY_SECONDS` | Notification | Initial mock behaviour and simulated delay |
| `ALLOW_MOCK_CONTROL` | Notification | Enables the demo-only mock-mode endpoint |

## Run tests and APIs

Business-rule tests are local to the service that owns each rule:

```powershell
python -m pytest
python scripts\end_to_end.py
```

The happy-path script creates its own inspector and work order, then confirms and notifies an assignment. Use Swagger UI on Work Order to upload JPEG/PNG inspection evidence after an assignment is confirmed: `POST /api/v1/work-orders/{id}/photos`. List and download endpoints are in the same OpenAPI page.

Export the four live OpenAPI specifications:

```powershell
python scripts\export_openapi.py
```

## Engineering challenge scripts

Run each script from the repository root while all services are healthy:

```powershell
python scripts\challenge_1_concurrency.py | Tee-Object evidence\challenge-1-concurrency\output.txt
python scripts\challenge_2_idempotency.py | Tee-Object evidence\challenge-2-idempotency\output.txt
python scripts\challenge_3a_resilience.py | Tee-Object evidence\challenge-3a-resilience\output.txt
python -m pytest | Tee-Object evidence\tests\output.txt
```

- Challenge 1 sends 20 assignments to one inspector slot and asserts exactly one HTTP 201, 19 HTTP 409 responses, and one database reservation.
- Challenge 2 sends simultaneous and sequential copies with one key, checks the stored response, rejects a changed payload, and verifies one reservation and notification.
- Challenge 3A forces provider failure, demonstrates bounded retries and a pending notification, recovers it manually, then simulates a committed delivery whose HTTP response is lost.

Copy the matching structured service logs from `.run/` into each evidence folder after a clean recorded run. Evidence READMEs explain the claims to capture.

## Repository layout

```text
README.md
docs/                       proposal, architecture, OpenAPI exports, final report PDF
services/<name>/
  src/                      API, business rules, data access, configuration
  tests/                    service-owned rule tests
  .env.example
  requirements.txt
scripts/                    startup, seed, end-to-end, and challenge scripts
evidence/
  challenge-1-concurrency/
  challenge-2-idempotency/
  challenge-3a-resilience/
  tests/
infra/                      database initialization only
```

See [the one-week scope](docs/proposal.md) and [architecture diagrams](docs/architecture.md). Photos, records, and outputs in the final submission must use synthetic, non-confidential data.
