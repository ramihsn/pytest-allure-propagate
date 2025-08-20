from __future__ import annotations

import allure  # type: ignore
import pytest


def test_step_propagate_caught_exception() -> None:
    with pytest.raises(ValueError, match="boom"):
        with allure.step("propagate caught", propagate=True):
            try:
                raise ValueError("boom")
            except ValueError:
                # Caught by user, but should still fail and propagate
                pass


def test_step_no_propagate_caught_exception() -> None:
    # Should not raise because user caught it and propagate=False (default)
    with allure.step("no propagate caught"):
        try:
            raise RuntimeError("nope")
        except RuntimeError:
            pass


def test_aggregate_step_runs_all_children_and_fails_after() -> None:
    executed: list[str] = []
    with pytest.raises(Exception) as excinfo:
        with allure.aggregate_step("aggregate"):
            executed.append("before-1")
            with allure.step("child 1"):
                executed.append("child-1-start")
                raise ValueError("first")
            executed.append("after-1")
            with allure.step("child 2"):
                executed.append("child-2-start")
                raise RuntimeError("second")
            executed.append("after-2")
            with allure.step("child 3 ok"):
                executed.append("child-3-start")
    message = str(excinfo.value)
    assert "2 exception(s)" in message
    assert "ValueError: first" in message and "RuntimeError: second" in message
    # All parts should have executed despite failures in child 1 and 2
    assert executed == [
        "before-1",
        "child-1-start",
        "after-1",
        "child-2-start",
        "after-2",
        "child-3-start",
    ]


def test_aggregate_captures_propagated_caught() -> None:
    # Inside aggregate, propagate=True should not interrupt flow, but be aggregated and raised at the end
    with pytest.raises(Exception) as excinfo:
        with allure.aggregate_step("aggregate propagate"):
            with allure.step("child caught", propagate=True):
                try:
                    raise KeyError("k")
                except KeyError:
                    pass
            with allure.step("child ok"):
                pass
    assert "KeyError" in str(excinfo.value)
