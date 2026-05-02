"""P3 / P1b: pacing between chained upstream calls (AkShare EM pools, etc.)."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

_DEFAULT = 0.35


def _float_env(name: str) -> Optional[float]:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def limit_up_chain_spacing_seconds(config: Optional[Dict[str, Any]] = None) -> float:
    """
    Seconds to sleep between consecutive AkShare calls in the limit-up approved chain.

    Resolution order: ``OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS`` env →
    ``data_sources.limit_up.upstream_chain_spacing_seconds`` →
    ``data_sources.intraday_tool_spacing_seconds`` → default ``0.35``.
    """
    ev = _float_env("OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS")
    if ev is not None and ev >= 0:
        return ev
    if isinstance(config, dict):
        ds = config.get("data_sources")
        if isinstance(ds, dict):
            lu = ds.get("limit_up")
            if isinstance(lu, dict) and "upstream_chain_spacing_seconds" in lu:
                try:
                    v = float(lu["upstream_chain_spacing_seconds"])
                    if v >= 0:
                        return v
                except (TypeError, ValueError, KeyError):
                    pass
            try:
                v2 = float(ds.get("intraday_tool_spacing_seconds", _DEFAULT))
                if v2 >= 0:
                    return v2
            except (TypeError, ValueError):
                pass
    return _DEFAULT


def sleep_limit_up_between_pools(config: Optional[Dict[str, Any]], *, after_step: int) -> None:
    """``after_step`` counts upstream attempts in chain (1 after em, 2 after previous, …). No-op when ``after_step < 1``."""
    if after_step < 1:
        return
    sec = limit_up_chain_spacing_seconds(config)
    if sec > 0:
        time.sleep(sec)


__all__ = ["limit_up_chain_spacing_seconds", "sleep_limit_up_between_pools"]
