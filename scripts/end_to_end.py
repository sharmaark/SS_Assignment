import json
import base64
from uuid import uuid4

from common import DISPATCH_URL, NOTIFICATION_URL, WORKFORCE_URL, WORK_ORDER_URL, create_inspector, create_work_order, request, require, set_mock_mode, wait_for_services


def main() -> None:
    wait_for_services()
    set_mock_mode("normal")
    inspector = create_inspector()
    work_order = create_work_order()
    payload = {"work_order_id": work_order["id"], "inspector_id": inspector["id"]}
    headers = {"Idempotency-Key": f"e2e-{uuid4()}", "X-Correlation-ID": f"e2e-{uuid4()}"}
    response = request(
        "POST",
        f"{DISPATCH_URL}/api/v1/assignments",
        json=payload,
        headers=headers,
    )
    assignment = require(response, 201)
    assert assignment["status"] == "CONFIRMED"
    assert assignment["notification_status"] == "SENT"
    assert response.headers["X-Correlation-ID"] == headers["X-Correlation-ID"]
    replay = require(request("POST", f"{DISPATCH_URL}/api/v1/assignments", json=payload, headers=headers), 201)
    assert replay == assignment
    changed = require(request(
        "POST", f"{DISPATCH_URL}/api/v1/assignments",
        json={**payload, "inspector_id": str(uuid4())}, headers=headers,
    ), 409)
    assert changed["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    persisted = require(request("GET", f"{DISPATCH_URL}/api/v1/assignments/{assignment['id']}"), 200)
    assert persisted["status"] == "CONFIRMED"
    assert persisted["reservation_id"] == assignment["reservation_id"]
    persisted_order = require(request("GET", f"{WORK_ORDER_URL}/api/v1/work-orders/{work_order['id']}"), 200)
    assert persisted_order["state"] == "ASSIGNED"
    assert persisted_order["assignment_id"] == assignment["id"]
    reservations = require(request("GET", f"{WORKFORCE_URL}/api/v1/reservations"), 200)["items"]
    matching_reservations = [item for item in reservations if item["assignment_id"] == assignment["id"]]
    assert len(matching_reservations) == 1
    assert matching_reservations[0]["id"] == assignment["reservation_id"]
    notifications = require(request("GET", f"{NOTIFICATION_URL}/api/v1/notifications"), 200)["items"]
    matching_notifications = [item for item in notifications if item["assignment_id"] == assignment["id"]]
    assert len(matching_notifications) == 1
    assert matching_notifications[0]["status"] == "SENT"

    one_pixel_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    photo = require(
        request(
            "POST",
            f"{WORK_ORDER_URL}/api/v1/work-orders/{work_order['id']}/photos",
            files={"photo": ("inspection.png", one_pixel_png, "image/png")},
        ),
        201,
    )
    photos = require(request("GET", f"{WORK_ORDER_URL}/api/v1/work-orders/{work_order['id']}/photos"), 200)
    assert len(photos["items"]) == 1
    assert photos["items"][0]["id"] == photo["id"]
    downloaded = request("GET", f"{WORK_ORDER_URL}/api/v1/photos/{photo['id']}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "image/png"
    assert downloaded.content == one_pixel_png
    print(json.dumps({
        "claim": "all service states agree; idempotent replay and GridFS evidence round trip verified",
        "assignment": assignment, "reservation": matching_reservations[0],
        "notification": matching_notifications[0], "photo": photo,
        "checks": ["confirmed work order", "single reservation", "single sent notification", "stored response replay", "changed payload rejected", "correlation header", "photo upload/list/download"],
    }, indent=2))


if __name__ == "__main__":
    main()
