"""Single lazy `ts.pro_api` for connector migration (northbound + fallback callers)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import tushare as ts  # type: ignore[import]
except Exception:  # pragma: no cover - optional dep in minimal envs
    ts = None  # type: ignore[assignment]

_PRO: Any = None


def get_tushare_pro() -> Optional[Any]:
    """Return shared ``pro_api`` or None if tushare missing / no token."""
    global _PRO
    if _PRO is not None:
        return _PRO
    if ts is None:
        return None
    token = (os.environ.get("TUSHARE_TOKEN") or "").strip()
    if not token:
        logger.debug("TUSHARE_TOKEN empty; pro_api unavailable")
        return None
    try:
        _PRO = ts.pro_api(token)
    except Exception as e:
        logger.warning("tushare pro_api init failed: %s", e)
        _PRO = None
    return _PRO


__all__ = ["get_tushare_pro"]
