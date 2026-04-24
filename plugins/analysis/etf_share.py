from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from plugins.data_collection.sentiment_common import normalize_contract


def _trade_date_default() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _meta(schema_name: str, layer: str, trade_date: str, quality_status: str) -> Dict[str, Any]:
    return {
        "schema_name": schema_name,
        "schema_version": "1.0.0",
        "task_id": "etf-rotation-research",
        "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
        "data_layer": layer,
        "generated_at": datetime.now().isoformat(),
        "trade_date": trade_date,
        "source_tools": ["akshare.fund_etf_scale_sse", "akshare.fund_etf_scale_szse"],
        "lineage_refs": [],
        "quality_status": quality_status,
    }


def _extract_share_series(df: pd.DataFrame, etf_code: str) -> List[Dict[str, Any]]:
    code_cols = [c for c in df.columns if "代码" in str(c)]
    date_cols = [c for c in df.columns if "日期" in str(c)]
    share_cols = [c for c in df.columns if "份额" in str(c)]
    if not date_cols or not share_cols:
        return []
    code_col = code_cols[0] if code_cols else None
    date_col = date_cols[0]
    share_col = share_cols[0]
    rows = df
    if code_col:
        rows = rows[rows[code_col].astype(str).str.contains(etf_code)]
    out = []
    for _, r in rows.iterrows():
        dt = str(r.get(date_col, "")).strip()
        share = pd.to_numeric(r.get(share_col), errors="coerce")
        if not dt or pd.isna(share):
            continue
        out.append({"date": dt, "share": float(share)})
    out.sort(key=lambda x: x["date"])
    return out


def tool_fetch_etf_share(etf_code: str, lookback_days: int = 60, trade_date: str | None = None) -> Dict[str, Any]:
    td = (trade_date or _trade_date_default()).strip()
    attempts: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    source = ""
    quality_status = "error"

    try:
        import akshare as ak  # type: ignore

        df = ak.fund_etf_scale_sse()
        sse = _extract_share_series(df, etf_code)
        if sse:
            records = sse[-max(1, int(lookback_days)) :]
            source = "fund_etf_scale_sse"
            quality_status = "ok"
            attempts.append({"source": source, "ok": True, "message": "ok"})
        else:
            attempts.append({"source": "fund_etf_scale_sse", "ok": False, "message": "empty"})
    except Exception as e:  # noqa: BLE001
        attempts.append({"source": "fund_etf_scale_sse", "ok": False, "message": str(e)[:200]})

    if not records:
        try:
            import akshare as ak  # type: ignore

            df = ak.fund_etf_scale_szse()
            szse = _extract_share_series(df, etf_code)
            if szse:
                records = szse[-max(1, int(lookback_days)) :]
                source = "fund_etf_scale_szse"
                quality_status = "degraded"
                attempts.append({"source": source, "ok": True, "message": "ok_but_limited"})
            else:
                attempts.append({"source": "fund_etf_scale_szse", "ok": False, "message": "empty"})
        except Exception as e:  # noqa: BLE001
            attempts.append({"source": "fund_etf_scale_szse", "ok": False, "message": str(e)[:200]})

    success = bool(records)
    if not success:
        quality_status = "error"
    payload = {
        "data": {
            "etf_code": etf_code,
            "trade_date": td,
            "lookback_days": lookback_days,
            "source": source,
            "records": records,
        },
        "_meta": _meta("raw_etf_share_timeseries_v1", "L1", td, quality_status),
        "quality_status": quality_status,
    }
    return normalize_contract(
        success=success,
        payload=payload,
        source=source or "etf_share",
        attempts=attempts,
        used_fallback=quality_status == "degraded",
        data_quality="fresh" if quality_status == "ok" else "partial",
        error_code=None if success else "UPSTREAM_FETCH_FAILED",
        error_message=None if success else "unable to fetch etf share",
        quality_data_type="fund_flow",
    )


def tool_calculate_share_trend(
    etf_code: str,
    windows: List[int] | None = None,
    trade_date: str | None = None,
) -> Dict[str, Any]:
    td = (trade_date or _trade_date_default()).strip()
    ws = windows or [5, 20, 60]
    raw = tool_fetch_etf_share(etf_code=etf_code, lookback_days=max(ws) + 5, trade_date=td)
    records = (((raw or {}).get("data") or {}).get("records") or []) if isinstance(raw, dict) else []
    quality_status = str((raw.get("quality_status") if isinstance(raw, dict) else None) or "error")
    attempts = raw.get("attempts") if isinstance(raw, dict) else []

    if not records:
        payload = {
            "data": {"etf_code": etf_code, "signal": "unknown", "divergence": "unknown", "windows": ws},
            "_meta": _meta("feat_etf_share_trend_v1", "L2", td, "error"),
            "quality_status": "error",
        }
        return normalize_contract(
            success=False,
            payload=payload,
            source="share_trend",
            attempts=attempts or [],
            used_fallback=False,
            data_quality="partial",
            error_code="INSUFFICIENT_DATA",
            error_message="no share records",
            quality_data_type="fund_flow",
        )

    series = pd.Series([float(x.get("share", 0.0)) for x in records if x.get("share") is not None])
    trend: Dict[str, float] = {}
    for w in ws:
        if len(series) > w:
            base = float(series.iloc[-w - 1]) if float(series.iloc[-w - 1]) != 0 else 1.0
            trend[f"chg_{w}d"] = float(series.iloc[-1] / base - 1.0)
        else:
            trend[f"chg_{w}d"] = 0.0
            quality_status = "degraded" if quality_status != "error" else "error"

    chg_5 = trend.get("chg_5d", 0.0)
    chg_20 = trend.get("chg_20d", 0.0)
    chg_60 = trend.get("chg_60d", 0.0)
    consistency = (1 if chg_5 > 0 else -1 if chg_5 < 0 else 0) + (1 if chg_20 > 0 else -1 if chg_20 < 0 else 0) + (1 if chg_60 > 0 else -1 if chg_60 < 0 else 0)
    signal = "accumulation" if consistency >= 2 else "distribution" if consistency <= -2 else "mixed"
    divergence = "price_up_share_down_or_unknown"
    trend_score = (chg_5 * 0.2) + (chg_20 * 0.3) + (chg_60 * 0.5)

    payload = {
        "data": {
            "etf_code": etf_code,
            "trade_date": td,
            "windows": ws,
            **trend,
            "consistency": consistency,
            "trend_score": trend_score,
            "signal": signal,
            "divergence": divergence,
        },
        "_meta": _meta("feat_etf_share_trend_v1", "L2", td, quality_status),
        "quality_status": quality_status,
    }
    return normalize_contract(
        success=True,
        payload=payload,
        source="share_trend",
        attempts=attempts or [],
        used_fallback=quality_status == "degraded",
        data_quality="fresh" if quality_status == "ok" else "partial",
        quality_data_type="fund_flow",
    )

