from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple, Type, cast
import threading
import warnings
import types
import sys


allure: Any
try:  # pragma: no cover - imported in test runtime
    import allure as _allure_mod

    allure = _allure_mod
    _import_error: Optional[Exception] = None
except Exception as import_error:  # pragma: no cover
    allure = None
    _import_error = import_error


ALLURE_REQUIRED_VERSION = "2.13.3"
_original_allure_step: Optional[Callable[[str], Any]] = None


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


TraceFunc = Callable[[types.FrameType, str, Any], Optional[Callable[..., Any]]]


class _PropagatingStep:
    def __init__(self, title: str, propagate: bool = False):
        if allure is None:  # pragma: no cover
            raise RuntimeError(f"allure is not importable: {_import_error}")
        self._title = title
        self._propagate = bool(propagate)
        # Use the original allure.step to avoid recursion after monkey patching
        assert _original_allure_step is not None, "Original allure.step not captured"
        self._inner_cm = _original_allure_step(title)
        self._caught_exc: Optional[Tuple[Type[BaseException], BaseException, types.TracebackType]] = None
        self._target_frame: Optional[types.FrameType] = None
        self._prev_global_trace: Optional[TraceFunc] = None
        self._prev_local_trace: Optional[TraceFunc] = None

    def __enter__(self) -> Any:
        result = self._inner_cm.__enter__()
        if self._propagate:

            def _tracer(frame: types.FrameType, event: str, arg: Any) -> Optional[Callable[..., Any]]:
                if event == "exception":
                    exc_type, exc_val, exc_tb = arg
                    if isinstance(exc_val, BaseException):
                        self._caught_exc = (exc_type, exc_val, exc_tb)
                return _tracer

            caller = sys._getframe(1)
            self._target_frame = caller
            self._prev_global_trace = cast(Optional[TraceFunc], sys.gettrace())
            self._prev_local_trace = cast(Optional[TraceFunc], caller.f_trace)
            sys.settrace(_tracer)
            caller.f_trace = _tracer
        return result

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> bool:
        # Remove tracer if installed
        if self._propagate:
            # Restore previous tracers
            if self._target_frame is not None:
                self._target_frame.f_trace = self._prev_local_trace
            sys.settrace(self._prev_global_trace)

        aggregate_stack = _get_aggregate_stack()
        in_aggregate = bool(aggregate_stack)

        # If an exception escaped the body, prefer that
        active_exc: Optional[Tuple[Type[BaseException], BaseException, types.TracebackType]]
        if exc_type is not None and exc_val is not None and exc_tb is not None:
            active_exc = (exc_type, exc_val, exc_tb)
        else:
            active_exc = self._caught_exc

        # If we detected a caught exception but nothing escaped and propagate is False, just finish normally
        if active_exc is None:
            return bool(self._inner_cm.__exit__(exc_type, exc_val, exc_tb))

        # Mark step failed by passing the exception into inner __exit__
        et, ev, etb = active_exc
        self._inner_cm.__exit__(et, ev, etb)

        if in_aggregate:
            # Collect and suppress to continue
            aggregate_stack[-1].exceptions.append(ev)
            return True

        # Outside aggregate
        if exc_type is not None:
            # Real exception escaped from body: let it propagate
            return False

        # No exception escaped but we saw a caught one and propagate=True: raise it now
        raise ev


class _AggregateStep:
    def __init__(self, title: str):
        if allure is None:  # pragma: no cover
            raise RuntimeError(f"allure is not importable: {_import_error}")
        self._title = title
        assert _original_allure_step is not None, "Original allure.step not captured"
        self._inner_cm = _original_allure_step(title)

    def __enter__(self) -> Any:
        _get_aggregate_stack().append(_AggregateState(self._title))
        return self._inner_cm.__enter__()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> bool:
        stack = _get_aggregate_stack()
        state = stack.pop() if stack else _AggregateState(self._title)

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
            self._inner_cm.__exit__(type(agg_err), agg_err, agg_err.__traceback__)
            # Raise aggregated error after marking step failed
            raise agg_err

        # Close the step normally (no errors aggregated)
        return bool(self._inner_cm.__exit__(local_exc_type, local_exc_val, local_exc_tb))


def aggregate_step(title: str) -> _AggregateStep:
    return _AggregateStep(title)


def _monkey_patch_allure() -> None:
    if allure is None:  # pragma: no cover
        return
    version = getattr(allure, "__version__", None)
    if version != ALLURE_REQUIRED_VERSION:
        warnings.warn(
            f"allure-pytest version mismatch: expected {ALLURE_REQUIRED_VERSION}, got {version}",
            RuntimeWarning,
            stacklevel=2,
        )

    original_step: Any = getattr(allure, "step", None)
    if original_step is None:
        return

    def step(title: str, propagate: bool = False) -> _PropagatingStep:
        return _PropagatingStep(title=title, propagate=propagate)

    # Install wrappers
    global _original_allure_step
    if _original_allure_step is None:
        _original_allure_step = cast(Callable[[str], Any], original_step)
    setattr(allure, "step", step)
    setattr(allure, "aggregate_step", aggregate_step)


def pytest_configure(config: Any) -> None:  # pragma: no cover - executed by pytest at runtime
    _monkey_patch_allure()
