import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from common import DISPATCH_URL, WORKFORCE_URL, create_inspector, create_work_order, request, require, set_mock_mode, wait_for_services


def main() -> None:
    wait_for_services()
    set_mock_mode("normal")
    inspector = create_inspector()
    slot = datetime.now(timezone.utc) + timedelta(days=8)
    work_orders = [create_work_order(slot) for _ in range(20)]

    def assign(work_order: dict):
        response = request(
            "POST",
            f"{DISPATCH_URL}/api/v1/assignments",
            json={"work_order_id": work_order["id"], "inspector_id": inspector["id"]},
            headers={"Idempotency-Key": f"concurrency-{uuid4()}"},
        )
        return {"status_code": response.status_code, "body": response.json()}

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(assign, work_orders))

    successes = [item for item in results if item["status_code"] == 201]
    rejected = [item for item in results if item["status_code"] == 409]
    reservations = require(request("GET", f"{WORKFORCE_URL}/api/v1/reservations"), 200)["items"]
    matching = [item for item in reservations if item["inspector_id"] == inspector["id"] and item["slot"].startswith(slot.date().isoformat())]

    assert len(successes) == 1, f"expected 1 success, got {len(successes)}"
    assert len(rejected) == 19, f"expected 19 conflicts, got {len(rejected)}"
    assert len(matching) == 1, f"expected 1 reservation, got {len(matching)}"
    output = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "claim": "20 concurrent requests for capacity 1 produce exactly 1 success",
        "successes": len(successes),
        "conflicts": len(rejected),
        "final_reservations": matching,
        "responses": results,
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
