import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from common import DISPATCH_URL, NOTIFICATION_URL, create_inspector, create_work_order, request, require, set_mock_mode, wait_for_services


def assign(work_order: dict, inspector: dict, label: str) -> dict:
    response = request(
        "POST",
        f"{DISPATCH_URL}/api/v1/assignments",
        json={"work_order_id": work_order["id"], "inspector_id": inspector["id"]},
        headers={"Idempotency-Key": f"{label}-{uuid4()}"},
    )
    return require(response, 201)


def main() -> None:
    wait_for_services()
    inspector = create_inspector()

    set_mock_mode("fail")
    first = assign(create_work_order(), inspector, "resilience-fail")
    assert first["status"] == "CONFIRMED"
    assert first["notification_status"] == "PENDING"

    set_mock_mode("normal")
    recovered = require(request("POST", f"{DISPATCH_URL}/api/v1/assignments/{first['id']}/retry-notification"), 200)
    assert recovered["notification_status"] == "SENT"

    set_mock_mode("commit_then_slow")
    second_slot = datetime.now(timezone.utc) + timedelta(days=9)
    second = assign(create_work_order(second_slot), inspector, "resilience-response-loss")
    assert second["notification_status"] == "SENT"
    notifications = require(request("GET", f"{NOTIFICATION_URL}/api/v1/notifications"), 200)["items"]
    matching = [item for item in notifications if item["assignment_id"] == second["id"]]
    assert len(matching) == 1
    assert matching[0]["status"] == "SENT"
    set_mock_mode("normal")

    print(json.dumps({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "claim": "bounded retries degrade gracefully and response-loss retries do not duplicate delivery",
        "provider_failure_assignment": first,
        "manual_recovery": recovered,
        "response_loss_assignment": second,
        "response_loss_notification_records": matching,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
