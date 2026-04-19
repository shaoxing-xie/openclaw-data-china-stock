"""
Batch-invoke a small allowlist of tools in one process (reduces agent round-trips).

Each item: {"id": optional key, "tool": "tool_fetch_...", "args": {...}}

并发：默认 max_workers=min(16, OPENCLAW_BATCH_MAX_WORKERS|4)；可通过 kwargs max_concurrent 覆盖。
"""

from __future__ import annotations

import importlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

_BATCH_IMPORTS = {
    "tool_metrics_snapshot": ("plugins.utils.tool_metrics", "tool_metrics_snapshot"),
    "tool_fetch_limit_up_stocks": ("plugins.data_collection.limit_up.fetch_limit_up", "tool_fetch_limit_up_stocks"),
    "tool_fetch_a_share_fund_flow": ("plugins.data_collection.a_share_fund_flow", "tool_fetch_a_share_fund_flow"),
    "tool_fetch_northbound_flow": ("plugins.data_collection.northbound", "tool_fetch_northbound_flow"),
    "tool_fetch_sector_data": ("plugins.data_collection.sector", "tool_fetch_sector_data"),
    "tool_fetch_market_data": ("plugins.merged.fetch_market_data", "tool_fetch_market_data"),
    "tool_fetch_stock_historical": (
        "plugins.data_collection.stock.fetch_historical",
        "tool_fetch_stock_historical",
    ),
    "tool_calculate_technical_indicators": (
        "plugins.data_collection.tools.tool_calculate_technical_indicators",
        "tool_calculate_technical_indicators",
    ),
    "tool_screen_equity_factors": ("plugins.analysis.equity_factor_screening", "tool_screen_equity_factors"),
}


def _run_single(i: int, item: Dict[str, Any]) -> Tuple[str, bool, Any]:
    if not isinstance(item, dict):
        return (f"idx_{i}", False, f"{i}: not an object")
    tid = str(item.get("tool") or "").strip()
    args = item.get("args") if isinstance(item.get("args"), dict) else {}
    key = str(item.get("id") or tid or f"idx_{i}")
    spec = _BATCH_IMPORTS.get(tid)
    if not spec:
        return (key, False, f"{key}: unsupported tool {tid!r}")
    try:
        mod = importlib.import_module(spec[0])
        fn = getattr(mod, spec[1])
        return (key, True, fn(**args))
    except Exception as e:  # noqa: BLE001
        return (key, False, f"{key}: {e}")


def tool_batch_fetch(
    items: Optional[List[Dict[str, Any]]] = None,
    max_concurrent: int = 0,
    **_: Any,
) -> Dict[str, Any]:
    items = items or []
    results: Dict[str, Any] = {}
    errors: List[str] = []

    if not items:
        return {
            "success": True,
            "results": {},
            "errors": [],
            "meta": {"count": 0, "ok_count": 0, "max_concurrent": 0},
        }

    mc = int(max_concurrent or os.environ.get("OPENCLAW_BATCH_MAX_WORKERS") or 4)
    mc = max(1, min(mc, 16))

    if len(items) == 1:
        key, ok, payload = _run_single(0, items[0])
        if ok:
            results[key] = payload
        else:
            errors.append(str(payload))
    else:
        with ThreadPoolExecutor(max_workers=mc) as ex:
            futs = {ex.submit(_run_single, i, item): i for i, item in enumerate(items)}
            for fut in as_completed(futs):
                key, ok, payload = fut.result()
                if ok:
                    results[key] = payload
                else:
                    errors.append(str(payload))

    return {
        "success": len(errors) == 0,
        "results": results,
        "errors": errors,
        "meta": {"count": len(items), "ok_count": len(results), "max_concurrent": mc},
    }
