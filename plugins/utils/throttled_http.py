"""
Limit concurrent upstream HTTP-style calls per process (AkShare / requests chains).

Set OPENCLAW_MAX_CONCURRENT_UPSTREAM (int, default 12); set to 0 to disable limiting.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_sem: threading.BoundedSemaphore | None = None
_sem_bound: int = -1


def _max_slots() -> int:
    raw = (os.getenv("OPENCLAW_MAX_CONCURRENT_UPSTREAM") or "12").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 12
    return max(0, n)


def _get_sem() -> threading.BoundedSemaphore | None:
    global _sem, _sem_bound
    mx = _max_slots()
    if mx == 0:
        return None
    with _lock:
        if _sem is None or _sem_bound != mx:
            _sem = threading.BoundedSemaphore(mx)
            _sem_bound = mx
    return _sem


@contextmanager
def upstream_slot() -> Iterator[None]:
    sem = _get_sem()
    if sem is None:
        yield
        return
    sem.acquire()
    try:
        yield
    finally:
        sem.release()


def run_bounded(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    with upstream_slot():
        return fn(*args, **kwargs)


def run_bounded_maybe_circuit(
    circuit_key: str | None,
    fn: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T | Dict[str, Any]:
    """
    在上游并发槽位内执行 fn；若给定 circuit_key 且熔断全局启用，
    OPEN 时返回 circuit_failure_payload（见 circuit_breaker），否则返回 fn 结果。
    """
    from plugins.utils.circuit_breaker import call_or_pass_through

    def _invoke() -> Any:
        return run_bounded(fn, *args, **kwargs)

    if not circuit_key:
        return _invoke()
    return call_or_pass_through(str(circuit_key), _invoke)
