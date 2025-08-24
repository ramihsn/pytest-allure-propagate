# tests/test_allure_ext_showcase.py
# Python 3.8+, allure-pytest>=2.13.3,<=2.14.1 baseline
# This file intentionally contains both passing and failing tests
# so you can see red/green/yellow statuses and nested steps in Allure UI.

from __future__ import annotations

import pytest
import logging
import allure

logger = logging.getLogger(__name__)


@pytest.fixture
def t_logger(request: pytest.FixtureRequest) -> logging.Logger:
    logger = logging.getLogger(request.node.name)
    return logger


def _do_work_ok():
    logger.info("do_work_ok")


def _do_work_fail(msg: str = "boom"):
    raise Exception(msg)


# =========================
# A) DEFAULT STEP BEHAVIOR
# =========================


def test_default_step_passes(t_logger: logging.Logger):
    t_logger.info("test_default_step_passes")
    """Expect: test PASSED, step S1 PASSED."""
    with allure.step("A1: default step passes (no exception)"):
        _do_work_ok()
    t_logger.info("test_default_step_passes done")


def test_default_step_caught_exception_is_green():
    """
    Upstream default: if you catch the error inside the step, step stays green.
    Expect: test PASSED, step S1 PASSED (greenwashed by design).
    """
    with allure.step("A3: default step caught exception remains PASSED"):
        try:
            _do_work_fail("caught-inside-step")
        except Exception:
            # swallowed on purpose
            pass


def test_default_step_uncaught_exception_fails():
    """Expect: test FAILED, step S1 FAILED."""
    with allure.step("A2: default step uncaught exception -> FAILED"):
        _do_work_fail("uncaught")


def test_default_nested_steps_uncaught_bubbles():
    """
    Expect: test FAILED, child C FAILED, parent P FAILED.
    """
    with allure.step("A4: parent P"):
        with allure.step("child C"):
            _do_work_fail("bubble-up")


def test_attachments_do_not_affect_status():
    """
    Expect: test PASSED, step PASSED; attachments visible.
    """
    with allure.step("A5: attachments demo"):
        allure.attach("plain text body", name="note.txt", attachment_type=allure.attachment_type.TEXT)
        allure.attach("<b>html!</b>", name="snippet.html", attachment_type=allure.attachment_type.HTML)
        _do_work_ok()


# ===================================
# B) step(..., propagate=...) SHOWCASE
# ===================================


def test_propagate_false_marks_failed_but_test_passes():
    """
    NEW: propagate=False (default) + caught error -> step FAILS, but test PASSES.
    Expect: test PASSED; step S1 FAILED (no greenwash).
    """
    with allure.step("B1: propagate=False -> step FAILS, test PASSES", propagate=False):
        try:
            _do_work_fail("handled-but-fail-step")
        except Exception as e:
            allure.attach(str(e), "error.txt", allure.attachment_type.TEXT)
            # swallowed, but step should still mark FAILED due to propagate=False semantics in extension


def test_propagate_true_reraises_after_context():
    """
    NEW: propagate=True + caught error -> step FAILS and exception is re-raised AFTER exiting the context.
    Expect: test FAILED; step S1 FAILED.
    """
    with allure.step("B2: propagate=True -> step FAILS and re-raises", propagate=True):
        try:
            _do_work_fail("will-reraise-after-context")
        except Exception:
            # swallowed NOW, but should be re-raised on context __exit__
            pass
    # should never reach here


def test_nested_propagate_behavior_bubbles_to_parent():
    """
    Child has propagate=True -> re-raise to parent; parent becomes FAILED.
    Expect: test FAILED; child FAILED; parent FAILED.
    """
    with allure.step("B3: parent P (will see child re-raise)"):
        with allure.step("child with propagate=True", propagate=True):
            try:
                _do_work_fail("child-error")
            except Exception:
                pass  # re-raised at exit of child context
        # should not run (child re-raise should bubble)
        _do_work_ok()


def test_propagate_true_no_exception_is_noop():
    """Expect: test PASSED; step PASSED."""
    with allure.step("B4: propagate=True but no error", propagate=True):
        _do_work_ok()


# ==========================================
# C) step(..., raise_on_parent=...) SHOWCASE
# ==========================================


def test_raise_on_parent_deferred_raise_single_child():
    """
    One child fails with raise_on_parent=True, others pass. Parent defers raise until exit.
    Expect: all children execute (C1 failed, C2/C3 passed); on parent exit parent FAILED; test FAILED.
    """
    with allure.step("C1: parent with deferred raise"):
        with allure.step("C1.child-1 (defer to parent)", raise_on_parent=True):
            try:
                _do_work_fail("child-1-fail")
            except Exception:
                pass  # recorded as failed; defer raising to parent
        with allure.step("C1.child-2 (pass)", raise_on_parent=True):
            _do_work_ok()
        with allure.step("C1.child-3 (pass)", raise_on_parent=False):
            _do_work_ok()


def test_raise_on_parent_aggregates_multiple_children():
    """
    Two children fail with raise_on_parent=True; parent should aggregate and fail at exit.
    Expect: C1 & C2 FAILED; parent FAILED; test FAILED; (message may include both causes).
    """
    with allure.step("C2: parent aggregates multiple child failures"):
        for i, msg in [(1, "e1"), (2, "e2")]:
            with allure.step(f"C2.child-{i}", raise_on_parent=True):
                try:
                    _do_work_fail(msg)
                except Exception:
                    pass
        with allure.step("C2.child-3 (pass)"):
            _do_work_ok()


def test_raise_on_parent_no_failures_no_raise():
    """Expect: all PASSED; test PASSED."""
    with allure.step("C3: parent with no failing children"):
        with allure.step("C3.child-1 (pass)", raise_on_parent=True):
            _do_work_ok()
        with allure.step("C3.child-2 (pass)"):
            _do_work_ok()


def test_raise_on_parent_without_parent_fails_test():
    """
    Edge: if a step uses raise_on_parent=True without a parent step, behavior should still fail test.
    Expect: this test FAILED; step FAILED at exit.
    """
    with allure.step("C4: lone step with raise_on_parent=True", raise_on_parent=True):
        try:
            _do_work_fail("lone-child-fail")
        except Exception:
            pass


# ==================================
# D) aggregate_step(...) SHOWCASE
# ==================================


def test_aggregate_runs_all_children_then_fails_if_any_failed():
    """
    Inside aggregate, all children run regardless of failures; final failure at end.
    Expect: C1 PASS, C2 FAIL, C3 PASS; A FAILED; test FAILED.
    """
    with allure.aggregate_step("D1: aggregate parent A"):
        with allure.step("A.child-1 (pass)"):
            _do_work_ok()
        with allure.step("A.child-2 (fail)"):
            _do_work_fail("agg-child-fail")
        with allure.step("A.child-3 (pass)"):
            _do_work_ok()


def test_aggregate_all_passes():
    """Expect: A PASSED; test PASSED."""
    with allure.aggregate_step("D2: aggregate all pass"):
        with allure.step("child-1"):
            _do_work_ok()
        with allure.step("child-2"):
            _do_work_ok()


def test_aggregate_collects_multiple_failures():
    """
    Expect: A FAILED; both failing children visible; test FAILED.
    """
    with allure.aggregate_step("D3: aggregate collects failures"):
        with allure.step("child-1 (fail)"):
            _do_work_fail("first")
        with allure.step("child-2 (fail)"):
            _do_work_fail("second")
        with allure.step("child-3 (pass)"):
            _do_work_ok()


def test_nested_aggregate_inside_aggregate():
    """
    Expect: inner B FAILED (one child fails), outer A FAILED; test FAILED.
    """
    with allure.aggregate_step("D4: outer A"):
        with allure.aggregate_step("inner B"):
            with allure.step("B.child-1 (fail)"):
                _do_work_fail("inner-fail")
            with allure.step("B.child-2 (pass)"):
                _do_work_ok()
        with allure.step("A.child-after-inner (pass)"):
            _do_work_ok()


def test_aggregate_with_child_propagate_true_does_not_abort_siblings():
    """
    A child step sets propagate=True and fails; aggregate must keep running siblings and fail at end.
    Expect: all children ran; failing child FAILED; A FAILED; test FAILED.
    """
    with allure.aggregate_step("D5: aggregate tolerates propagate=True child"):
        with allure.step("child-1 (pass)"):
            _do_work_ok()
        # This child would normally re-raise on exit; aggregate should intercept and continue.
        with allure.step("child-2 (propagate=True fail)", propagate=True):
            try:
                _do_work_fail("propagate-in-aggregate")
            except Exception:
                pass
        with allure.step("child-3 (pass)"):
            _do_work_ok()


# ==========================================
# E) MIXED CASES & VISUALS (OPTIONAL EXTRAS)
# ==========================================


def test_mixing_raise_on_parent_and_aggregate():
    """
    Mixing semantics: children inside aggregate use raise_on_parent=True and fail.
    Aggregate should still control final failure timing (no mid-body abort).
    Expect: children FAILED; A FAILED at end; test FAILED.
    """
    with allure.aggregate_step("E1: aggregate + raise_on_parent children"):
        with allure.step("child-1 (ROP fail)", raise_on_parent=True):
            try:
                _do_work_fail("rop-1")
            except Exception:
                pass
        with allure.step("child-2 (pass)"):
            _do_work_ok()
        with allure.step("child-3 (ROP fail)", raise_on_parent=True):
            try:
                _do_work_fail("rop-2")
            except Exception:
                pass


def test_visual_demo_with_attachments_and_nesting():
    """
    Purely for UI demo richness: nested steps, attachments, mixed outcomes.
    Expect: parent FAILED due to one child; attachments visible.
    """
    with allure.step("E2: visual demo parent"):
        with allure.step("info block"):
            allure.attach("context line 1\ncontext line 2", "context.txt", allure.attachment_type.TEXT)
        with allure.step("do ok"):
            _do_work_ok()
        with allure.step("do fail"):
            allure.attach("<i>about to fail</i>", "warn.html", allure.attachment_type.HTML)
            _do_work_fail("visual-failure")
        with allure.step("cleanup (still runs if failure uncaught?)"):
            # NOTE: If previous failure is uncaught, this may not run.
            # Keep for demonstration; in practice wrap with try/except if you *must* run.
            _do_work_ok()
