"""Run all four local service processes; databases must already be running."""

import subprocess
import sys
import time
import os


SERVICES = [
    ("work-order", "services.work_order.src.api:app", int(os.getenv("WORK_ORDER_PORT", "8001"))),
    ("workforce", "services.workforce.src.api:app", int(os.getenv("WORKFORCE_PORT", "8002"))),
    ("dispatch", "services.dispatch.src.api:app", int(os.getenv("DISPATCH_PORT", "8003"))),
    ("notification", "services.notification.src.api:app", int(os.getenv("NOTIFICATION_PORT", "8004"))),
]


def main() -> None:
    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        for name, application, port in SERVICES:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    application,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ]
            )
            processes.append((name, process))
            print(f"started {name} on port {port} (PID {process.pid})", flush=True)
        while all(process.poll() is None for _, process in processes):
            time.sleep(0.5)
        failures = [(name, process.returncode) for name, process in processes if process.poll() is not None]
        raise RuntimeError(f"service process exited: {failures}")
    except KeyboardInterrupt:
        pass
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
