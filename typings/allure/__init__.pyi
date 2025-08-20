from typing import Any, ContextManager, Optional, Type
from types import TracebackType


class _AnyContextManager(ContextManager[Any]):
    def __enter__(self) -> Any: ...

    def __exit__(self,
                 __t: Optional[Type[BaseException]],
                 __v: Optional[BaseException],
                 __tb: Optional[TracebackType]) -> bool: ...


def step(title: str, propagate: bool = ...) -> _AnyContextManager: ...


def aggregate_step(title: str) -> _AnyContextManager: ...
