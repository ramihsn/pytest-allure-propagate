from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple, Type, cast
from importlib import metadata
import threading
import warnings
import types
import sys
import os
import logging


allure: Any
try:  # pragma: no cover - imported in test runtime
    import allure as _allure_mod

    allure = _allure_mod
    _import_error: Optional[Exception] = None
except Exception as import_error:  # pragma: no cover
    allure = None
    _import_error = import_error


ALLURE_REQUIRED_VERSION = "2.13.4"
_original_allure_step: Optional[Callable[[str], Any]] = None

# Runtime toggle for source-logger step event logging
_log_steps_enabled: bool = False
_debug_trace: bool = bool(os.environ.get("ALLURE_EXT_DEBUG_TRACE"))


def set_step_logging(enabled: bool) -> None:
    """
    Enable/disable logging of step start/end using the caller module's logger.

    This affects both allure.step(...) and allure.aggregate_step(...).
    """
    global _log_steps_enabled
    _log_steps_enabled = bool(enabled)


def _resolve_logger_for_frame(frame: types.FrameType) -> logging.Logger:
    module_name_obj = frame.f_globals.get("__name__", "__main__")
    module_name = module_name_obj if isinstance(module_name_obj, str) else "__main__"
    return logging.getLogger(module_name)


def _maybe_log(logger: Optional[logging.Logger], level: int, message: str) -> None:
    if not _log_steps_enabled:
        return
    if logger is None:
        return
    try:
        logger.log(level, message)
    except Exception:
        # Never interfere with test execution due to logging issues
        pass


class AggregateError(Exception):
    def __init__(self, title: str, exceptions: List[BaseException]):
        self.title = title
        self.exceptions = exceptions
        summary = ", ".join(f"{type(e).__name__}: {e}" for e in exceptions)
        super().__init__(f"{len(exceptions)} exception(s) occurred during '{title}': {summary}")


class _AggregateState:
    def __init__(self, title: str):
        self.title = title
        self.exceptions: List[BaseException] = []


_thread_local: threading.local = threading.local()


def _get_aggregate_stack() -> List[_AggregateState]:
    stack = getattr(_thread_local, "aggregate_stack", None)
    if stack is None:
        stack = []
        _thread_local.aggregate_stack = stack
    return stack


def _get_propagate_stack() -> List["_PropagatingStep"]:
    stack = getattr(_thread_local, "propagate_stack", None)
    if stack is None:
        stack = []
        _thread_local.propagate_stack = stack
    return stack


TraceFunc = Callable[[types.FrameType, str, Any], Optional[Callable[..., Any]]]


class _PropagatingStep:
    def __init__(self, title: str, propagate: bool = False, raise_on_parent: bool = False):
        if allure is None:  # pragma: no cover
            raise RuntimeError(f"allure is not importable: {_import_error}")
        self._title = title
        self._propagate = bool(propagate)
        self._raise_on_parent = bool(raise_on_parent)
        # Use the original allure.step to avoid recursion after monkey patching
        assert _original_allure_step is not None, "Original allure.step not captured"
        self._inner_cm = _original_allure_step(title)
        self._caught_exc: Optional[Tuple[Type[BaseException], BaseException, types.TracebackType]] = None
        self._observed_caught_exc: Optional[Tuple[Type[BaseException], BaseException, types.TracebackType]] = None
        self._target_frame: Optional[types.FrameType] = None
        self._prev_global_trace: Optional[TraceFunc] = None
        self._installed_global_trace: bool = False
        self._prev_local_trace: Optional[TraceFunc] = None
        self._logger: Optional[logging.Logger] = None

    def __enter__(self) -> Any:
        result = self._inner_cm.__enter__()
        if self._propagate:
            # Track active propagating steps to broadcast caught exceptions to parents
            _get_propagate_stack().append(self)

            def _tracer(frame: types.FrameType, event: str, arg: Any) -> Optional[Callable[..., Any]]:
                # Capture any exception observed within the step body
                if event == "exception":
                    exc_type, exc_val, exc_tb = arg
                    if _debug_trace:
                        try:
                            name = getattr(exc_type, "__name__", str(exc_type))
                            print(f"[ALLURE_EXT DEBUG] step={self._title!r} saw exception {name}: {exc_val}")
                        except Exception:
                            pass
                    # Ignore control-flow sentinel exceptions which may appear in pytest internals
                    try:
                        is_control_flow_exc = issubclass(exc_type, (StopIteration, GeneratorExit))
                    except Exception:
                        is_control_flow_exc = False
                    if isinstance(exc_val, BaseException) and not is_control_flow_exc:
                        exc_info = (exc_type, exc_val, exc_tb)
                        # Preserve the first meaningful exception only
                        if self._caught_exc is None:
                            self._caught_exc = exc_info
                        # Broadcast first meaningful exception to all open propagating steps (parents)
                        for step in list(_get_propagate_stack()):
                            if step._observed_caught_exc is None:
                                step._observed_caught_exc = exc_info
                # Chain to any previously installed local tracer so that
                # parent propagating steps can also observe this exception
                # when nested propagating steps install their own tracer.
                if self._prev_local_trace is not None:
                    try:
                        result = self._prev_local_trace(frame, event, arg)
                        # If previous tracer returns something other than None, use that
                        if result is not None:
                            return result
                    except Exception:
                        # Do not interfere with program flow if previous tracer errs
                        pass
                # Only return self to continue tracing - avoid infinite recursion
                return _tracer

            caller = sys._getframe(1)
            self._target_frame = caller
            # Acquire a logger tied to the caller's module for source-origin logs
            self._logger = _resolve_logger_for_frame(caller)
            _maybe_log(self._logger, logging.INFO, f"[STEP START] {self._title!r}")
            # Save previously installed tracers
            self._prev_global_trace = cast(Optional[TraceFunc], sys.gettrace())
            self._prev_local_trace = cast(Optional[TraceFunc], caller.f_trace)

            # Ensure tracing is enabled so that frame.f_trace receives events.
            # Under tools like coverage (CTracer), Python-level local tracers are not invoked unless a
            # Python-level global tracer is active. Force-install a minimal Python tracer for the duration
            # of this step, then restore the previous tracer on exit.
            def _global_stub(frame: types.FrameType, event: str, arg: Any) -> Optional[Callable[..., Any]]:
                return None

            sys.settrace(_global_stub)
            self._installed_global_trace = True

            # Install local tracer for this frame to observe exceptions
            caller.f_trace = _tracer
        else:
            # Even when propagate is disabled, we still support START logging
            caller = sys._getframe(1)
            self._target_frame = caller
            self._logger = _resolve_logger_for_frame(caller)
            _maybe_log(self._logger, logging.INFO, f"[STEP START] {self._title!r}")
        return result

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> bool:
        # Remove tracer if installed
        if self._propagate:
            # Pop from propagate stack
            stack = _get_propagate_stack()
            if stack and stack[-1] is self:
                stack.pop()
            else:
                # Defensive: remove self if present elsewhere
                try:
                    stack.remove(self)
                except ValueError:
                    pass
            # Restore previous tracers
            if self._target_frame is not None:
                self._target_frame.f_trace = self._prev_local_trace
            # Restore previous global tracer exactly as it was before entry
            if self._installed_global_trace:
                try:
                    sys.settrace(self._prev_global_trace)
                finally:
                    self._installed_global_trace = False

        aggregate_stack = _get_aggregate_stack()
        in_aggregate = bool(aggregate_stack)

        # If an exception escaped the body, prefer that; else use any observed caught exception
        active_exc: Optional[Tuple[Type[BaseException], BaseException, types.TracebackType]]
        if exc_type is not None and exc_val is not None and exc_tb is not None:
            active_exc = (exc_type, exc_val, exc_tb)
        else:
            active_exc = self._caught_exc or self._observed_caught_exc

        # If we detected a caught exception but nothing escaped and propagate is False, just finish normally
        if active_exc is None:
            try:
                return bool(self._inner_cm.__exit__(exc_type, exc_val, exc_tb))
            finally:
                _maybe_log(self._logger, logging.INFO, f"[STEP END] {self._title!r} - PASS")

        # There was an exception observed or escaping
        et, ev, etb = active_exc
        if _debug_trace:
            try:
                print(f"[ALLURE_EXT DEBUG] __exit__ active_exc for {self._title!r}: {type(ev).__name__}: {ev}")
            except Exception:
                pass

        # Ensure parents know about this failure even if tracer missed the exact event
        try:
            for step in list(_get_propagate_stack()):
                if step is not self and step._observed_caught_exc is None:
                    step._observed_caught_exc = (et, ev, etb)
        except Exception:
            pass

        if in_aggregate:
            # Under aggregate, always mark the step as failed (not broken), regardless of exception type
            ae = AssertionError(str(ev))
            self._inner_cm.__exit__(type(ae), ae, ae.__traceback__)
            _maybe_log(self._logger, logging.INFO, f"[STEP END] {self._title!r} - FAIL")
            # Collect the original exception and suppress to continue siblings
            aggregate_stack[-1].exceptions.append(ev)
            return True

        # Not in aggregate: mark step according to the real exception
        self._inner_cm.__exit__(et, ev, etb)
        _maybe_log(self._logger, logging.INFO, f"[STEP END] {self._title!r} - FAIL")

        # Outside aggregate
        if exc_type is not None:
            # Real exception escaped from body: let it propagate
            return False

        # No exception escaped but we saw a caught one and propagate=True
        # Marked failed already above; only raise if configured to do so
        if self._propagate and self._raise_on_parent:
            raise ev
        # Otherwise, continue without raising
        return True


class _AggregateStep:
    def __init__(self, title: str):
        if allure is None:  # pragma: no cover
            raise RuntimeError(f"allure is not importable: {_import_error}")
        self._title = title
        assert _original_allure_step is not None, "Original allure.step not captured"
        self._inner_cm = _original_allure_step(title)
        self._logger: Optional[logging.Logger] = None

    def __enter__(self) -> Any:
        _get_aggregate_stack().append(_AggregateState(self._title))
        caller = sys._getframe(1)
        self._logger = _resolve_logger_for_frame(caller)
        _maybe_log(self._logger, logging.INFO, f"[STEP START] {self._title!r}")
        return self._inner_cm.__enter__()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> bool:
        stack = _get_aggregate_stack()
        state = stack.pop() if stack else _AggregateState(self._title)
        in_parent_aggregate = bool(stack)

        # If the aggregate body raised, collect that exception and suppress for now
        local_exc_type = exc_type
        local_exc_val = exc_val
        local_exc_tb = exc_tb
        if local_exc_type is not None and local_exc_val is not None and local_exc_tb is not None:
            state.exceptions.append(local_exc_val)
            local_exc_type, local_exc_val, local_exc_tb = None, None, None

        if state.exceptions:
            # Mark the aggregate step as failed with an aggregated error
            agg_err = AggregateError(self._title, state.exceptions)
            # Force allure status to failed for the aggregate step
            ae = AssertionError(str(agg_err))
            self._inner_cm.__exit__(type(ae), ae, ae.__traceback__)
            _maybe_log(self._logger, logging.INFO, f"[STEP END] {self._title!r} - FAIL")
            if in_parent_aggregate:
                # Defer raising to the parent aggregate; collect into parent and continue
                stack[-1].exceptions.append(agg_err)
                return True
            # No parent aggregate: raise aggregated error now
            raise agg_err

        # Close the step normally (no errors aggregated)
        try:
            return bool(self._inner_cm.__exit__(local_exc_type, local_exc_val, local_exc_tb))
        finally:
            _maybe_log(self._logger, logging.INFO, f"[STEP END] {self._title!r} - PASS")


def aggregate_step(title: str) -> _AggregateStep:
    return _AggregateStep(title)


def _monkey_patch_allure() -> None:
    if allure is None:  # pragma: no cover
        return
    try:
        version = metadata.version("allure-pytest")
    except metadata.PackageNotFoundError:  # pragma: no cover
        version = None
    if version != ALLURE_REQUIRED_VERSION:
        warnings.warn(
            f"allure-pytest version mismatch: expected {ALLURE_REQUIRED_VERSION}, got {version}",
            RuntimeWarning,
            stacklevel=2,
        )

    original_step: Any = getattr(allure, "step", None)
    if original_step is None:
        return

    def step(title: str, propagate: bool = False, raise_on_parent: bool = False) -> _PropagatingStep:
        return _PropagatingStep(title=title, propagate=propagate, raise_on_parent=raise_on_parent)

    # Install wrappers
    global _original_allure_step
    if _original_allure_step is None:
        _original_allure_step = cast(Callable[[str], Any], original_step)
    setattr(allure, "step", step)
    setattr(allure, "aggregate_step", aggregate_step)


def pytest_addoption(parser: Any) -> None:  # pragma: no cover - executed by pytest at collection time
    try:
        group = parser.getgroup("allure-pytest-ext")
    except Exception:
        group = parser
    group.addoption(
        "--allure-log-steps",
        action="store_true",
        default=False,
        help="Log step start/end using the caller module's logger (info level)",
    )
    # INI: allure_log_steps = true/false
    parser.addini("allure_log_steps", "bool: log step start/end from source module loggers", default=False)


def pytest_configure(config: Any) -> None:  # pragma: no cover - executed by pytest at runtime
    _monkey_patch_allure()
    # Resolve logging toggle from CLI/INI/env (any truthy enables)
    env_enabled = os.environ.get("ALLURE_EXT_LOG_STEPS") or os.environ.get("ALLURE_LOG_STEPS")
    ini_enabled = False
    try:
        ini_enabled = bool(config.getini("allure_log_steps"))
    except Exception:
        ini_enabled = False
    cli_enabled = False
    try:
        cli_enabled = bool(getattr(config.option, "allure_log_steps", False))
    except Exception:
        cli_enabled = False
    set_step_logging(bool(env_enabled) or ini_enabled or cli_enabled)
