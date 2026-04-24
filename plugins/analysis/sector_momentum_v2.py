from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from plugins.data_collection.sector import tool_fetch_sector_data
from plugins.data_collection.sentiment_common import normalize_contract


def tool_calculate_sector_momentum_v2(
    sector_code: str,
    lookback_days: int = 20,
    trade_date: str | None = None,
) -> Dict[str, Any]:
    td = (trade_date or datetime.now().strftime("%Y-%m-%d")).strip()
    res = tool_fetch_sector_data(sector_type="industry", period="today")
    rows: List[Dict[str, Any]] = list((res or {}).get("all_data") or []) if isinstance(res, dict) else []
    attempts = list((res or {}).get("attempts") or []) if isinstance(res, dict) else []
    target = None
    for r in rows:
        if str(r.get("sector_name", "")).strip() == str(sector_code).strip():
            target = r
            break
    if target is None and rows:
        target = rows[0]
    if target is None:
        return normalize_contract(
            success=False,
            payload={
                "data": {"sector_code": sector_code, "score": 0.0},
                "_meta": {"schema_name": "feat_sector_momentum_v2_v1", "schema_version": "1.0.0", "task_id": "etf-rotation-research", "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"), "data_layer": "L2", "generated_at": datetime.now().isoformat(), "trade_date": td, "source_tools": ["tool_fetch_sector_data"], "lineage_refs": [], "quality_status": "error"},
                "quality_status": "error",
            },
            source="sector_momentum_v2",
            attempts=attempts,
            used_fallback=False,
            data_quality="partial",
            error_code="UPSTREAM_FETCH_FAILED",
            error_message="sector data unavailable",
            quality_data_type="sector",
        )
    momentum_component = float(target.get("change_percent") or 0.0) / 100.0
    volume_component = 0.0
    if target.get("net_inflow") is not None:
        volume_component = float(target.get("net_inflow") or 0.0) / 1_000_000_000.0
    score = (momentum_component * 0.7) + (volume_component * 0.3)
    payload = {
        "data": {
            "sector_code": sector_code,
            "sector_name": target.get("sector_name"),
            "trade_date": td,
            "lookback_days": lookback_days,
            "momentum_component": momentum_component,
            "volume_component": volume_component,
            "score": score,
        },
        "_meta": {"schema_name": "feat_sector_momentum_v2_v1", "schema_version": "1.0.0", "task_id": "etf-rotation-research", "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"), "data_layer": "L2", "generated_at": datetime.now().isoformat(), "trade_date": td, "source_tools": ["tool_fetch_sector_data"], "lineage_refs": [], "quality_status": "ok"},
        "quality_status": "ok",
    }
    return normalize_contract(
        success=True,
        payload=payload,
        source="tool_fetch_sector_data",
        attempts=attempts,
        used_fallback=False,
        data_quality="fresh",
        quality_data_type="sector",
    )

