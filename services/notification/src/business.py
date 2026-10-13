from typing import Literal


MockMode = Literal["normal", "fail", "slow", "commit_then_slow"]


def should_commit_before_delay(mode: MockMode) -> bool:
    return mode in {"normal", "slow", "commit_then_slow"}


def should_delay(mode: MockMode) -> bool:
    return mode in {"slow", "commit_then_slow"}


def should_fail(mode: MockMode) -> bool:
    return mode == "fail"
