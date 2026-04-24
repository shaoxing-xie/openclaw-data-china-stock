from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from plugins.data_collection.sector import tool_fetch_sector_data
from plugins.data_collection.stock.fundamentals_extended import tool_fetch_a_share_universe
from plugins.data_collection.stock.fetch_historical import tool_fetch_stock_historical
from plugins.data_collection.sentiment_common import normalize_contract


def _pct(records: List[Dict[str, Any]], days: int) -> float:
    if len(records) <= days:
        return 0.0
    last = float(records[-1].get("close") or records[-1].get("收盘") or 0.0)
    base = float(records[-days - 1].get("close") or records[-days - 1].get("收盘") or 0.0)
    if base == 0:
        return 0.0
    return (last / base) - 1.0


def tool_calculate_sector_leadership(
    sector_code: str,
    lookback_days: int = 60,
    top_k: int = 5,
    weighting_scheme: str = "equal",
    trade_date: str | None = None,
) -> Dict[str, Any]:
    td = (trade_date or datetime.now().strftime("%Y-%m-%d")).strip()
    sector_res = tool_fetch_sector_data(sector_type="industry", period="today")
    rows = (((sector_res or {}).get("all_data") or []) if isinstance(sector_res, dict) else [])
    target = None
    for r in rows:
        if str(r.get("sector_name", "")).strip() == str(sector_code).strip():
            target = r
            break
    if target is None and rows:
        target = rows[0]
    attempts = list(sector_res.get("attempts") or []) if isinstance(sector_res, dict) else []

    if target is None:
        return normalize_contract(
            success=False,
            payload={
                "data": {"sector_code": sector_code, "leaders": []},
                "_meta": {"schema_name": "feat_sector_leadership_v1", "schema_version": "1.0.0", "task_id": "etf-rotation-research", "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"), "data_layer": "L2", "generated_at": datetime.now().isoformat(), "trade_date": td, "source_tools": ["tool_fetch_sector_data"], "lineage_refs": [], "quality_status": "error"},
                "quality_status": "error",
            },
            source="sector_leadership",
            attempts=attempts,
            used_fallback=False,
            data_quality="partial",
            error_code="UPSTREAM_FETCH_FAILED",
            error_message="sector unavailable",
            quality_data_type="sector",
        )

    leader_name = str(target.get("top_gainer_name") or target.get("领涨股") or "").strip()
    if not leader_name:
        # fall back to sector name text as proxy id
        leader_name = str(target.get("sector_name") or "unknown")
    uni = tool_fetch_a_share_universe(max_rows=0)
    urows = (((uni or {}).get("data") or {}).get("records") or []) if isinstance(uni, dict) else []
    code = ""
    for r in urows:
        n = str(r.get("name") or r.get("stock_name") or "").strip()
        if n == leader_name:
            code = str(r.get("code") or r.get("stock_code") or "").strip()
            break
    if not code and urows:
        code = str((urows[0].get("code") or urows[0].get("stock_code") or "")).strip()

    hist = tool_fetch_stock_historical(stock_code=code, period="daily", lookback_days=max(lookback_days, 70))
    hrows = (((hist or {}).get("data") or {}).get("records") or []) if isinstance(hist, dict) else []
    m5 = _pct(hrows, 5)
    m20 = _pct(hrows, 20)
    m60 = _pct(hrows, 60)
    leadership_score = (m5 * 0.2) + (m20 * 0.3) + (m60 * 0.5)
    quality = "degraded"
    if code and hrows:
        quality = "ok"
    attempts.extend((uni.get("attempts") or []) if isinstance(uni, dict) else [])
    attempts.extend((hist.get("attempts") or []) if isinstance(hist, dict) else [])
    payload = {
        "data": {
            "sector_code": sector_code,
            "sector_name": target.get("sector_name"),
            "trade_date": td,
            "top_k": top_k,
            "weighting_scheme": weighting_scheme,
            "leaders": [{"symbol": code, "name": leader_name, "momentum_5d": m5, "momentum_20d": m20, "momentum_60d": m60}],
            "leadership_score": leadership_score,
            "concentration": "high" if abs(leadership_score) > 0.05 else "mid",
            "proxy_mode": True,
        },
        "_meta": {"schema_name": "feat_sector_leadership_v1", "schema_version": "1.0.0", "task_id": "etf-rotation-research", "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"), "data_layer": "L2", "generated_at": datetime.now().isoformat(), "trade_date": td, "source_tools": ["tool_fetch_sector_data", "tool_fetch_a_share_universe", "tool_fetch_stock_historical"], "lineage_refs": [], "quality_status": quality},
        "quality_status": quality,
    }
    return normalize_contract(
        success=True,
        payload=payload,
        source="leadership_proxy",
        attempts=attempts,
        used_fallback=True,
        data_quality="partial" if quality == "degraded" else "fresh",
        quality_data_type="sector",
    )

