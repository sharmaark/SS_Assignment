import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

WORK_ORDER_URL = os.getenv("WORK_ORDER_URL", "http://localhost:8001")
WORKFORCE_URL = os.getenv("WORKFORCE_URL", "http://localhost:8002")
DISPATCH_URL = os.getenv("DISPATCH_URL", "http://localhost:8003")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")


def request(method: str, url: str, **kwargs) -> httpx.Response:
    response = httpx.request(method, url, timeout=15, **kwargs)
    return response


def require(response: httpx.Response, expected: int | tuple[int, ...]) -> dict:
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        raise RuntimeError(f"{response.request.method} {response.request.url} -> {response.status_code}: {response.text}")
    return response.json()


def wait_for_services() -> None:
    for name, url in {
        "work-order": WORK_ORDER_URL,
        "workforce": WORKFORCE_URL,
        "dispatch": DISPATCH_URL,
        "notification": NOTIFICATION_URL,
    }.items():
        try:
            require(request("GET", f"{url}/health"), 200)
        except Exception as exc:
            raise RuntimeError(f"{name} is not ready at {url}: {exc}") from exc


def create_inspector() -> dict:
    payload = {
        "name": f"Inspector {uuid4().hex[:6]}",
        "skills": ["ELECTRICAL"],
        "min_longitude": 77.0,
        "min_latitude": 12.0,
        "max_longitude": 78.0,
        "max_latitude": 13.0,
    }
    return require(request("POST", f"{WORKFORCE_URL}/api/v1/inspectors", json=payload), 201)


def create_work_order(slot: datetime | None = None) -> dict:
    payload = {
        "asset_id": f"POLE-{uuid4().hex[:8]}",
        "longitude": 77.5946,
        "latitude": 12.9716,
        "required_skill": "ELECTRICAL",
        "slot": (slot or datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    }
    return require(request("POST", f"{WORK_ORDER_URL}/api/v1/work-orders", json=payload), 201)


def set_mock_mode(mode: str) -> dict:
    return require(request("PUT", f"{NOTIFICATION_URL}/api/v1/mock-mode", json={"mode": mode}), 200)
