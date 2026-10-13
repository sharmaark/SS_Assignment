import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

from common import DISPATCH_URL, NOTIFICATION_URL, WORKFORCE_URL, create_inspector, create_work_order, request, require, set_mock_mode, wait_for_services


def main() -> None:
    wait_for_services()
    set_mock_mode("normal")
    inspector = create_inspector()
    work_order = create_work_order()
    key = f"idempotency-{uuid4()}"
    payload = {"work_order_id": work_order["id"], "inspector_id": inspector["id"]}

    def submit(body=payload):
        response = request("POST", f"{DISPATCH_URL}/api/v1/assignments", json=body, headers={"Idempotency-Key": key})
        return {"status_code": response.status_code, "body": response.json()}

    with ThreadPoolExecutor(max_workers=2) as pool:
        simultaneous = list(pool.map(lambda _: submit(), range(2)))
    replay = submit()
    changed = submit({"work_order_id": work_order["id"], "inspector_id": str(uuid4())})

    assert [item["status_code"] for item in simultaneous] == [201, 201]
    assignment_ids = {item["body"]["id"] for item in simultaneous}
    assignment_ids.add(replay["body"]["id"])
    assert len(assignment_ids) == 1
    assert changed["status_code"] == 409

    assignment_id = next(iter(assignment_ids))
    reservations = require(request("GET", f"{WORKFORCE_URL}/api/v1/reservations"), 200)["items"]
    notifications = require(request("GET", f"{NOTIFICATION_URL}/api/v1/notifications"), 200)["items"]
    matching_reservations = [item for item in reservations if item["assignment_id"] == assignment_id]
    matching_notifications = [item for item in notifications if item["assignment_id"] == assignment_id]
    assert len(matching_reservations) == 1
    assert len(matching_notifications) == 1

    print(json.dumps({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "claim": "simultaneous and sequential repeats return one stored result",
        "simultaneous": simultaneous,
        "sequential_replay": replay,
        "changed_payload": changed,
        "final_reservations": matching_reservations,
        "final_notifications": matching_notifications,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
