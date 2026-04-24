from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from plugins.data_collection.sector import tool_fetch_sector_data
from plugins.data_collection.sentiment_common import normalize_contract


def tool_calculate_sector_breadth(
    sector_code: str,
    lookback_days: int = 20,
    trade_date: str | None = None,
) -> Dict[str, Any]:
    td = (trade_date or datetime.now().strftime("%Y-%m-%d")).strip()
    out = tool_fetch_sector_data(sector_type="industry", period="today")
    rows = (((out or {}).get("all_data") or []) if isinstance(out, dict) else [])
    attempts = out.get("attempts") if isinstance(out, dict) else []

    target = None
    for r in rows:
        if str(r.get("sector_name", "")).strip() == str(sector_code).strip():
            target = r
            break
    if target is None and rows:
        target = rows[0]

    if target is None:
        payload = {
            "data": {
                "sector_code": sector_code,
                "trade_date": td,
                "lookback_days": lookback_days,
                "breadth_ratio": 0.0,
                "advance_count": 0,
                "decline_count": 0,
                "signal": "unknown",
            },
            "_meta": {
                "schema_name": "feat_sector_breadth_v1",
                "schema_version": "1.0.0",
                "task_id": "etf-rotation-research",
                "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "data_layer": "L2",
                "generated_at": datetime.now().isoformat(),
                "trade_date": td,
                "source_tools": ["tool_fetch_sector_data"],
                "lineage_refs": [],
                "quality_status": "error",
            },
            "quality_status": "error",
        }
        return normalize_contract(
            success=False,
            payload=payload,
            source="sector_breadth",
            attempts=attempts or [],
            used_fallback=False,
            data_quality="partial",
            error_code="UPSTREAM_FETCH_FAILED",
            error_message="sector data unavailable",
            quality_data_type="sector",
        )

    adv = int(target.get("rise_count") or 0)
    dec = int(target.get("fall_count") or 0)
    total = max(1, adv + dec)
    breadth_ratio = float(adv) / float(total)
    signal = "broadening" if breadth_ratio >= 0.6 else "neutral" if breadth_ratio >= 0.45 else "narrowing"
    quality_status = "ok" if (adv + dec) > 0 else "degraded"
    payload = {
        "data": {
            "sector_code": sector_code,
            "sector_name": target.get("sector_name"),
            "trade_date": td,
            "lookback_days": lookback_days,
            "advance_count": adv,
            "decline_count": dec,
            "breadth_ratio": breadth_ratio,
            "signal": signal,
        },
        "_meta": {
            "schema_name": "feat_sector_breadth_v1",
            "schema_version": "1.0.0",
            "task_id": "etf-rotation-research",
            "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "data_layer": "L2",
            "generated_at": datetime.now().isoformat(),
            "trade_date": td,
            "source_tools": ["tool_fetch_sector_data"],
            "lineage_refs": [],
            "quality_status": quality_status,
        },
        "quality_status": quality_status,
    }
    return normalize_contract(
        success=True,
        payload=payload,
        source="tool_fetch_sector_data",
        attempts=attempts or [],
        used_fallback=quality_status == "degraded",
        data_quality="fresh" if quality_status == "ok" else "partial",
        quality_data_type="sector",
    )

