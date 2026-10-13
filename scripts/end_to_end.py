import json
import base64
from uuid import uuid4

from common import DISPATCH_URL, WORK_ORDER_URL, create_inspector, create_work_order, request, require, set_mock_mode, wait_for_services


def main() -> None:
    wait_for_services()
    set_mock_mode("normal")
    inspector = create_inspector()
    work_order = create_work_order()
    response = request(
        "POST",
        f"{DISPATCH_URL}/api/v1/assignments",
        json={"work_order_id": work_order["id"], "inspector_id": inspector["id"]},
        headers={"Idempotency-Key": f"e2e-{uuid4()}"},
    )
    assignment = require(response, 201)
    assert assignment["status"] == "CONFIRMED"
    assert assignment["notification_status"] == "SENT"

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
    print(json.dumps({"claim": "main flow confirms, notifies, and stores GridFS evidence", "assignment": assignment, "photo": photo}, indent=2))


if __name__ == "__main__":
    main()
