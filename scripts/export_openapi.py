import json
from pathlib import Path

import httpx

from common import DISPATCH_URL, NOTIFICATION_URL, WORKFORCE_URL, WORK_ORDER_URL, wait_for_services


def main() -> None:
    wait_for_services()
    output = Path("docs/openapi")
    output.mkdir(parents=True, exist_ok=True)
    for name, url in {
        "work-order": WORK_ORDER_URL,
        "workforce": WORKFORCE_URL,
        "dispatch": DISPATCH_URL,
        "notification": NOTIFICATION_URL,
    }.items():
        specification = httpx.get(f"{url}/openapi.json", timeout=10).json()
        (output / f"{name}.json").write_text(json.dumps(specification, indent=2), encoding="utf-8")
        print(f"exported {output / f'{name}.json'}")


if __name__ == "__main__":
    main()
