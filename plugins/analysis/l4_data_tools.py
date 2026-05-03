"""
L4-data tools: deterministic JSON bundles with advisory-free notes.

- valuation_context: snapshot from financials view
- pe_ttm_percentile: historical PE_TTM distribution (reporting dates) vs latest in window
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from plugins.analysis.equity_factor_screening import _norm_code_6
from plugins.data_collection.financials import fetch_stock_pe_ttm_timeseries
from plugins.data_collection.stock.unified_stock_views import fetch_stock_valuation_snapshot_view


def tool_l4_valuation_context(
    stock_code: str,
    trade_date: str | None = None,
    **_: Any,
) -> Dict[str, Any]:
    """
    Return L4_data JSON: latest valuation-related fields from financials snapshot.

    Does not output buy/sell guidance; ``note`` is factual only.
    """
    td = (trade_date or datetime.now().strftime("%Y-%m-%d")).strip()
    code6 = _norm_code_6(stock_code)
    snap = fetch_stock_valuation_snapshot_view(code6)
    fin = snap.get("data") if isinstance(snap.get("data"), dict) else {}
    ok = bool(snap.get("success")) and bool(fin)
    q = "ok" if ok else "degraded"
    metrics = {
        k: fin.get(k)
        for k in ("pe", "pb", "ps", "roe", "debt_to_assets", "gross_margin")
        if fin.get(k) is not None
    }
    note = (
        "估值相关字段来自 tool_fetch_stock_financials 快照；历史分位见 tool_l4_pe_ttm_percentile。"
        if ok
        else "上游估值快照不可用，仅返回元数据。"
    )
    return {
        "success": ok,
        "message": "l4_valuation_context ok" if ok else "l4_valuation_context degraded",
        "quality_status": q,
        "_meta": {
            "schema_name": "valuation_context_v1",
            "schema_version": "1.0.0",
            "task_id": "l4-valuation-context",
            "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "data_layer": "L4_data",
            "generated_at": datetime.now().isoformat(),
            "trade_date": td,
            "lineage_refs": ["fetch_stock_valuation_snapshot_view", "tool_fetch_stock_financials"],
            "quality_status": q,
        },
        "data": {
            "entity_id": f"stk:{code6}",
            "as_of_date": td,
            "metrics": metrics,
            "note": note,
        },
    }


def _percentile_of_current(values: List[float], current: Optional[float]) -> Optional[float]:
    arr = [float(v) for v in values if v is not None and v == v and abs(float(v)) < 1e4]
    if len(arr) < 3 or current is None or not (current == current):
        return None
    below = sum(1 for x in arr if x < current)
    eq = sum(1 for x in arr if x == current)
    return (below + 0.5 * eq) / len(arr) * 100.0


def tool_l4_pe_ttm_percentile(
    stock_code: str,
    trade_date: str | None = None,
    window_years: int = 5,
    **_: Any,
) -> Dict[str, Any]:
    """
    L4_data: PE_TTM 在 ``window_years`` 报告期样本内的经验分位（0–100），基于东方财富按报告期指标表。
    非投资建议；样本过少时 ``quality_status=degraded``。
    """
    td = (trade_date or datetime.now().strftime("%Y-%m-%d")).strip()
    code6 = _norm_code_6(stock_code)
    ts = fetch_stock_pe_ttm_timeseries(code6)
    points = ts.get("points") if isinstance(ts.get("points"), list) else []
    if not ts.get("success") or not points:
        return {
            "success": False,
            "message": ts.get("error") or "no pe history",
            "quality_status": "degraded",
            "_meta": {
                "schema_name": "pe_ttm_percentile_band_v1",
                "schema_version": "1.0.0",
                "task_id": "l4-pe-ttm-percentile",
                "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "data_layer": "L4_data",
                "generated_at": datetime.now().isoformat(),
                "trade_date": td,
                "lineage_refs": ["fetch_stock_pe_ttm_timeseries", "stock_financial_analysis_indicator_em"],
                "quality_status": "degraded",
            },
            "data": {
                "entity_id": f"stk:{code6}",
                "window_years": int(window_years),
                "pe_ttm_current": None,
                "percentile_0_100": None,
                "sample_size": 0,
                "note": "无法构建 PE 历史序列",
            },
        }

    rows: List[Dict[str, Any]] = []
    for p in points:
        if not isinstance(p, dict):
            continue
        rd = p.get("report_date")
        pev = p.get("pe_ttm")
        try:
            dt = pd.to_datetime(rd, errors="coerce")
        except Exception:
            dt = pd.NaT
        if pd.isna(dt):
            continue
        rows.append({"dt": dt, "report_date": str(rd), "pe_ttm": float(pev) if pev is not None else None})

    wy = max(1, min(int(window_years or 5), 20))
    cutoff = pd.Timestamp.now(tz=None) - pd.DateOffset(years=wy)
    in_win = [r for r in rows if r["dt"] >= cutoff and r.get("pe_ttm") is not None]
    in_win.sort(key=lambda r: r["dt"])
    pes = [float(r["pe_ttm"]) for r in in_win if r["pe_ttm"] is not None]
    current = pes[-1] if pes else None
    pct = _percentile_of_current(pes, current)
    q = "ok" if len(pes) >= 8 and pct is not None else "degraded"
    note = (
        f"基于最近约 {wy} 年内 {len(pes)} 个报告期 PE_TTM；分位为样本内经验分位。"
        if pct is not None
        else "样本不足或 PE 无效，未计算分位。"
    )
    return {
        "success": pct is not None,
        "message": "l4_pe_ttm_percentile ok" if q == "ok" else "l4_pe_ttm_percentile degraded",
        "quality_status": q,
        "_meta": {
            "schema_name": "pe_ttm_percentile_band_v1",
            "schema_version": "1.0.0",
            "task_id": "l4-pe-ttm-percentile",
            "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "data_layer": "L4_data",
            "generated_at": datetime.now().isoformat(),
            "trade_date": td,
            "lineage_refs": ["fetch_stock_pe_ttm_timeseries"],
            "quality_status": q,
        },
        "data": {
            "entity_id": f"stk:{code6}",
            "window_years": wy,
            "pe_ttm_current": current,
            "percentile_0_100": round(pct, 4) if pct is not None else None,
            "sample_size": len(pes),
            "note": note,
        },
    }
