import json
from datetime import datetime, timedelta, timezone

from common import create_inspector, create_work_order, wait_for_services


def main() -> None:
    wait_for_services()
    inspector = create_inspector()
    work_order = create_work_order(datetime.now(timezone.utc) + timedelta(days=7))
    print(json.dumps({"inspector": inspector, "work_order": work_order}, indent=2, default=str))


if __name__ == "__main__":
    main()
