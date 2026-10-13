from services.notification.src.business import should_delay, should_fail


def test_normal_delivery_has_no_failure_or_delay():
    assert not should_fail("normal")
    assert not should_delay("normal")


def test_failure_mode_is_explicit():
    assert should_fail("fail")
    assert not should_fail("slow")


def test_slow_modes_are_detected():
    assert should_delay("slow")
    assert should_delay("commit_then_slow")
