from __future__ import annotations

import logging
import re

import allure

from allure_pytest_ext.plugin import set_step_logging


def _find_messages(records, pattern: str) -> list[str]:
    regex = re.compile(pattern)
    return [r.getMessage() for r in records if regex.search(r.getMessage() or "")]  # type: ignore[attr-defined]


def test_step_logging_is_disabled_by_default(caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.clear()
    with allure.step("log-off step test"):
        pass
    msgs = _find_messages(caplog.records, r"STEP (START|END) '")
    assert msgs == []


def test_step_logging_on_emits_start_and_end_from_source_logger(caplog) -> None:
    try:
        set_step_logging(True)
        caplog.set_level(logging.INFO)
        caplog.clear()
        with allure.step("sample step title"):
            pass
        # Expect exactly two messages for this step
        title = "sample step title"
        msgs = _find_messages(caplog.records, r"^\[STEP (START|END)\] '%s'" % re.escape(title))
        assert any(m == "[STEP START] 'sample step title'" for m in msgs)
        assert any(m == "[STEP END] 'sample step title' - PASS" for m in msgs)
        # Ensure records originate from the current test module's logger
        assert all(r.name == __name__ for r in caplog.records if r.getMessage().startswith("[STEP "))
    finally:
        set_step_logging(False)


def test_step_logging_failed_end_on_caught_error_with_propagate_true(caplog) -> None:
    try:
        set_step_logging(True)
        caplog.set_level(logging.INFO)
        caplog.clear()
        with allure.step("failing step", propagate=True):
            try:
                raise ValueError("boom")
            except ValueError:
                pass
        msgs = _find_messages(caplog.records, r"^\[STEP END\] 'failing step' - FAIL")
        assert msgs, msgs
        assert all(r.name == __name__ for r in caplog.records if r.getMessage().startswith("[STEP "))
    finally:
        set_step_logging(False)


def test_aggregate_step_logging_emits_start_and_end(caplog) -> None:
    try:
        set_step_logging(True)
        caplog.set_level(logging.INFO)
        caplog.clear()
        with allure.aggregate_step("parent aggregate"):
            with allure.step("child pass"):
                pass
        title = "parent aggregate"
        msgs = _find_messages(caplog.records, rf"^\[STEP (START|END)\] '{re.escape(title)}'")
        assert any(m == "[STEP START] 'parent aggregate'" for m in msgs)
        assert any(m == "[STEP END] 'parent aggregate' - PASS" for m in msgs)
        assert all(r.name == __name__ for r in caplog.records if r.getMessage().startswith("[STEP "))
    finally:
        set_step_logging(False)
