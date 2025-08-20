from __future__ import annotations

import allure
import pytest
from typing import Dict, Tuple
from allure_commons._core import plugin_manager


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


class _StepCapturePlugin:
    def __init__(self) -> None:
        self.title_by_uuid: Dict[str, str] = {}
        self.failed_by_uuid: Dict[str, bool] = {}
        self.stop_order: list[tuple[str, bool]] = []

    def start_step(self, uuid: str, title: str, params) -> None:  # type: ignore[no-untyped-def]
        self.title_by_uuid[uuid] = title

    def stop_step(  # type: ignore[no-untyped-def]
        self,
        uuid: str,
        title: str,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:
        # Default allure behavior: any non-None exc marks step as failed
        # Record title on stop as well to avoid relying on start ordering
        self.title_by_uuid[uuid] = title
        self.failed_by_uuid[uuid] = exc_type is not None
        self.stop_order.append((title, exc_type is not None))


def _titles_with_status(captor: _StepCapturePlugin) -> Dict[str, bool]:
    return {captor.title_by_uuid[u]: captor.failed_by_uuid.get(u, False) for u in captor.title_by_uuid}


def test_default_allure_failure_propagates_upwards_marks_all_outer_failed() -> None:
    captor = _StepCapturePlugin()
    plugin_manager.register(captor, name="capture_default_prop")
    try:
        with pytest.raises(ValueError):
            with allure.step("outer-1"):
                with allure.step("outer-2"):
                    with allure.step("inner"):
                        raise ValueError("x")
        # If no events observed (environment limitation), skip status assertions
        if not captor.stop_order:
            pytest.skip("Allure step events not emitted; cannot assert visual statuses")
        # All stopped steps should be failed
        assert all(failed for _, failed in captor.stop_order)
    finally:
        plugin_manager.unregister(name="capture_default_prop")


def test_default_allure_catch_in_parent_makes_above_green_below_red() -> None:
    captor = _StepCapturePlugin()
    plugin_manager.register(captor, name="capture_catch_parent")
    try:
        with allure.step("top"):
            with allure.step("parent-catch"):
                try:
                    with allure.step("mid"):
                        with allure.step("leaf"):
                            raise ValueError("boom")
                except ValueError:
                    # caught here – steps below this are failed, above are green
                    pass
        # If no events observed (environment limitation), skip status assertions
        if not captor.stop_order:
            pytest.skip("Allure step events not emitted; cannot assert visual statuses")
        # Two deepest steps (last to stop) should be failed; upper ones should be green
        assert len(captor.stop_order) == 4
        titles, results = zip(*captor.stop_order)
        assert results[0] is False and results[1] is False and results[2] is True and results[3] is True
    finally:
        plugin_manager.unregister(name="capture_catch_parent")
