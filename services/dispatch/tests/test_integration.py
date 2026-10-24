"""Real PostgreSQL/MongoDB integration; enable with GEOINSPECT_INTEGRATION=1.

Only HTTP transport is in-process. Service routes, business rules, constraints,
GridFS, and Dispatch's cross-connection execution locks use real implementations.
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import os
from threading import Event
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from gridfs import GridFSBucket
from sqlalchemy import create_engine, text

from services.dispatch.src import api as dispatch
from services.dispatch.src.clients import DownstreamError, DownstreamTimeout
from services.dispatch.src.data import DispatchRepository
from services.notification.src import api as notification
from services.notification.src.data import NotificationRepository
from services.work_order.src import api as work_order
from services.work_order.src.data import WorkOrderRepository
from services.workforce.src import api as workforce
from services.workforce.src.data import WorkforceRepository


pytestmark = pytest.mark.skipif(
    os.getenv("GEOINSPECT_INTEGRATION") != "1", reason="set GEOINSPECT_INTEGRATION=1 with Compose databases running"
)


@pytest.fixture
def system(monkeypatch):
    # Fresh, generated namespaces; no shared data is erased during cleanup.
    namespace = f"dispatch_test_{uuid4().hex}"
    engines = []
    repositories = []
    mongo_repositories = []
    with ExitStack() as cleanup:
        for module, repository_type, database_url in [
            (dispatch, DispatchRepository, dispatch.settings.dispatch_database_url),
            (workforce, WorkforceRepository, workforce.settings.workforce_database_url),
        ]:
            admin_engine = create_engine(database_url)
            engines.append(admin_engine)
            with admin_engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{namespace}"'))
            cleanup.callback(drop_schema, admin_engine, namespace)
            scoped_url = admin_engine.url.update_query_dict({"options": f"-csearch_path={namespace}"})
            repository = repository_type(scoped_url)
            repositories.append(repository)
            monkeypatch.setattr(module, "repository", repository)

        orders = WorkOrderRepository(work_order.settings.work_order_mongodb_url, work_order.settings.work_order_mongodb_database)
        orders.work_orders = orders.db[f"{namespace}_orders"]
        orders.photos = GridFSBucket(orders.db, bucket_name=f"{namespace}_photos")
        notifications = NotificationRepository(notification.settings.notification_mongodb_url, notification.settings.notification_mongodb_database)
        notifications.notifications = notifications.db[f"{namespace}_notifications"]
        mongo_repositories.extend([orders, notifications])
        for repository in mongo_repositories:
            cleanup.callback(drop_test_collections, repository.db, repository.client, namespace)
        # Work Order's list/index paths address db.inspection_photos directly.
        orders.db = SimpleNamespace(inspection_photos=orders.db[f"{namespace}_photos"])
        monkeypatch.setattr(work_order, "repository", orders)
        monkeypatch.setattr(notification, "repository", notifications)
        monkeypatch.setattr(notification.app.state, "mock_mode", "normal")
        monkeypatch.setattr(dispatch.settings, "retry_base_seconds", 0)
        monkeypatch.setattr(notification.settings, "mock_delay_seconds", 0)

        with ExitStack() as stack:
            order_api = stack.enter_context(TestClient(work_order.app))
            workforce_api = stack.enter_context(TestClient(workforce.app))
            notification_api = stack.enter_context(TestClient(notification.app))
            dispatch_api = stack.enter_context(TestClient(dispatch.app))
            routes = {
                dispatch.clients.work_order_url: order_api,
                dispatch.clients.workforce_url: workforce_api,
                dispatch.clients.notification_url: notification_api,
            }
            calls = []

            def post(url, *, json, headers, timeout):
                parts = urlsplit(url)
                calls.append((parts.path, headers["X-Correlation-ID"]))
                return routes[f"{parts.scheme}://{parts.netloc}"].post(parts.path, json=json, headers=headers)

            monkeypatch.setattr(httpx, "post", post)
            inspector = workforce_api.post("/api/v1/inspectors", json={
                "name": "Integration inspector", "skills": ["ELECTRICAL"],
                "min_longitude": 77, "min_latitude": 12, "max_longitude": 78, "max_latitude": 13,
            })
            assert inspector.status_code == 201, inspector.text
            order = order_api.post("/api/v1/work-orders", json={
                "asset_id": namespace, "longitude": 77.5946, "latitude": 12.9716,
                "required_skill": "ELECTRICAL", "slot": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            })
            assert order.status_code == 201, order.text
            state = SimpleNamespace(
                dispatch=dispatch_api, orders=order_api, workforce=workforce_api, notifications=notification_api,
                repository=dispatch.repository, calls=calls, key=f"integration-{uuid4()}",
                payload={"work_order_id": order.json()["id"], "inspector_id": inspector.json()["id"]},
            )
            yield state

        for repository in repositories:
            repository.engine.dispose()
            if hasattr(repository, "lock_engine"):
                repository.lock_engine.dispose()
    for engine in engines:
        engine.dispose()


def drop_schema(engine, namespace):
    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{namespace}" CASCADE'))


def drop_test_collections(database, client, namespace):
    for name in database.list_collection_names():
        if name.startswith(f"{namespace}_"):
            database.drop_collection(name)
    client.close()


def submit(system, payload=None):
    return system.dispatch.post("/api/v1/assignments", json=payload or system.payload, headers={
        "Idempotency-Key": system.key, "X-Correlation-ID": "dispatch-integration",
    })


def assert_single_assignment(system, response):
    assert response.status_code == 201, response.text
    assignment = response.json()
    assert assignment["status"] == "CONFIRMED"
    assert assignment["notification_status"] == "SENT"
    assert len(system.dispatch.get("/api/v1/assignments").json()["items"]) == 1
    reservations = system.workforce.get("/api/v1/reservations").json()["items"]
    notifications = system.notifications.get("/api/v1/notifications").json()["items"]
    assert len(reservations) == len(notifications) == 1
    assert reservations[0]["assignment_id"] == notifications[0]["assignment_id"] == assignment["id"]
    order = system.orders.get(f"/api/v1/work-orders/{system.payload['work_order_id']}").json()
    assert order["state"] == "ASSIGNED"
    assert order["assignment_id"] == assignment["id"]
    return assignment


def test_happy_path_replay_correlation_and_gridfs_evidence(system):
    response = submit(system)
    assert_single_assignment(system, response)
    calls = list(system.calls)
    replay = submit(system)
    assert (replay.status_code, replay.json()) == (201, response.json())
    assert system.calls == calls
    assert all(correlation == "dispatch-integration" for _, correlation in calls)
    changed = submit(system, {**system.payload, "inspector_id": str(uuid4())})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    path = f"/api/v1/work-orders/{system.payload['work_order_id']}/photos"
    photo = system.orders.post(path, files={"photo": ("inspection.png", png, "image/png")})
    assert photo.status_code == 201, photo.text
    assert system.orders.get(path).json()["items"][0]["id"] == photo.json()["id"]
    assert system.orders.get(f"/api/v1/photos/{photo.json()['id']}").content == png


@pytest.mark.parametrize("operation,stage", [
    ("claim_work_order", "CREATED"), ("reserve", "WORK_ORDER_CLAIMED"), ("confirm_work_order", "SLOT_RESERVED"),
])
def test_lost_committed_response_resumes_with_the_same_key(system, monkeypatch, operation, stage):
    original = getattr(dispatch.clients, operation)

    def lose_response(*args, **kwargs):
        original(*args, **kwargs)
        monkeypatch.setattr(dispatch.clients, operation, original)
        raise DownstreamTimeout(operation)

    monkeypatch.setattr(dispatch.clients, operation, lose_response)
    first = submit(system)
    assert first.status_code == 503
    pending = system.dispatch.get("/api/v1/assignments").json()["items"][0]
    assert pending["stage"] == stage
    assert system.repository.get_idempotency_result(system.key) is None
    resumed = assert_single_assignment(system, submit(system))
    assert resumed["id"] == pending["id"]


@pytest.mark.parametrize("operation", ["claim_work_order", "reserve"])
def test_downstream_server_error_does_not_become_a_permanent_rejection(system, monkeypatch, operation):
    original = getattr(dispatch.clients, operation)

    def fail_once(*args, **kwargs):
        monkeypatch.setattr(dispatch.clients, operation, original)
        raise DownstreamError(operation, 503, {"error": {"code": "UNAVAILABLE"}})

    monkeypatch.setattr(dispatch.clients, operation, fail_once)
    assert submit(system).status_code == 503
    assert_single_assignment(system, submit(system))


def test_rejected_reservation_releases_claim_and_replays_error(system):
    system.payload["inspector_id"] = str(uuid4())
    rejected = submit(system)
    assert rejected.status_code == 404
    assert rejected.json()["error"]["code"] == "INSPECTOR_NOT_FOUND"
    calls = list(system.calls)
    assert submit(system).json() == rejected.json()
    assert system.calls == calls
    order = system.orders.get(f"/api/v1/work-orders/{system.payload['work_order_id']}").json()
    assert order["state"] == "OPEN"
    assert order["assignment_id"] is None
    assert system.dispatch.get("/api/v1/assignments").json()["items"][0]["status"] == "REJECTED"


def test_failed_compensation_can_be_retried(system, monkeypatch):
    system.payload["inspector_id"] = str(uuid4())
    original = dispatch.clients.release_work_order

    def fail_once(*args, **kwargs):
        monkeypatch.setattr(dispatch.clients, "release_work_order", original)
        raise DownstreamTimeout("work-order")

    monkeypatch.setattr(dispatch.clients, "release_work_order", fail_once)
    assert submit(system).status_code == 503
    assert system.repository.get_idempotency_result(system.key) is None
    assert submit(system).status_code == 404
    order = system.orders.get(f"/api/v1/work-orders/{system.payload['work_order_id']}").json()
    assert order["state"] == "OPEN"


def test_processing_notification_stays_pending_and_can_be_recovered(system, monkeypatch):
    original = dispatch.clients.notify
    attempts = []

    def processing(payload, correlation):
        attempts.append(payload["delivery_key"])
        return {"status": "PROCESSING"}

    monkeypatch.setattr(dispatch.clients, "notify", processing)
    response = submit(system)
    assert response.status_code == 201
    assert response.json()["status"] == "CONFIRMED"
    assert response.json()["notification_status"] == "PENDING"
    assert len(attempts) == dispatch.settings.notification_max_attempts
    assert len(set(attempts)) == 1
    monkeypatch.setattr(dispatch.clients, "notify", original)
    recovered = system.dispatch.post(f"/api/v1/assignments/{response.json()['id']}/retry-notification")
    assert recovered.json()["notification_status"] == "SENT"
    assert submit(system).json() == response.json()  # Stored response stays immutable.


def test_notification_provider_failure_and_manual_recovery(system):
    notification.app.state.mock_mode = "fail"
    response = submit(system)
    assert response.status_code == 201
    assert response.json()["status"] == "CONFIRMED"
    assert response.json()["notification_status"] == "PENDING"
    notifications = system.notifications.get("/api/v1/notifications").json()["items"]
    assert notifications[0]["attempts"] == dispatch.settings.notification_max_attempts
    notification.app.state.mock_mode = "normal"
    recovered = system.dispatch.post(f"/api/v1/assignments/{response.json()['id']}/retry-notification")
    assert recovered.json()["notification_status"] == "SENT"
    notifications = system.notifications.get("/api/v1/notifications").json()["items"]
    assert len(notifications) == 1
    calls = list(system.calls)
    repeated = system.dispatch.post(f"/api/v1/assignments/{response.json()['id']}/retry-notification")
    assert repeated.json()["notification_status"] == "SENT"
    assert system.calls == calls


def test_recovery_after_confirmed_checkpoint_does_not_reclaim_or_notify_twice(system, monkeypatch):
    original = system.repository.complete

    def crash_once(*args, **kwargs):
        monkeypatch.setattr(system.repository, "complete", original)
        raise RuntimeError("simulated worker failure before response persistence")

    monkeypatch.setattr(system.repository, "complete", crash_once)
    with pytest.raises(RuntimeError):
        submit(system)
    calls = list(system.calls)
    assert_single_assignment(system, submit(system))
    assert system.calls == calls


def test_simultaneous_duplicates_return_one_stored_result(system):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: submit(system), range(8)))
    assignment = assert_single_assignment(system, responses[0])
    assert all(response.status_code == 201 and response.json() == assignment for response in responses)
    assert len(system.calls) == 4  # Claim, reserve, confirm, notify exactly once.


def test_duplicate_wait_is_bounded_and_does_not_start_another_orchestrator(system, monkeypatch):
    entered, release = Event(), Event()
    original = dispatch.clients.notify

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(dispatch.settings, "idempotency_wait_seconds", 0)
    monkeypatch.setattr(dispatch.clients, "notify", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(submit, system)
        try:
            assert entered.wait(10)
            duplicate = submit(system)
            assert duplicate.status_code == 202
        finally:
            release.set()
        completed = running.result(timeout=10)
    assert_single_assignment(system, completed)
    assert duplicate.json()["id"] == completed.json()["id"]
    assert submit(system).json() == completed.json()


def test_execution_lock_is_exclusive_across_repository_instances_and_released_on_error(system):
    other = DispatchRepository(system.repository.engine.url)
    try:
        with pytest.raises(RuntimeError):
            with system.repository.execution_lock(system.key) as first:
                assert first
                with other.execution_lock(system.key) as second:
                    assert not second
                raise RuntimeError("worker failed")
        with other.execution_lock(system.key) as acquired:
            assert acquired
    finally:
        other.engine.dispose()
        other.lock_engine.dispose()
