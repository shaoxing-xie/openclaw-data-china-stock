"""
中证指数(CSIndex)日频数据采集工具。

数据源:
- akshare.stock_zh_index_hist_csindex
"""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import pandas as pd

from plugins.utils.source_registry import with_source_meta

try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except Exception:  # noqa: BLE001
    AKSHARE_AVAILABLE = False


DATE_FORMAT = "%Y-%m-%d"
REQUIRED_COLS = ("日期", "开盘", "最高", "最低", "收盘")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_input_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return text
    if len(text) == 10 and "-" in text:
        try:
            return datetime.strptime(text, DATE_FORMAT).strftime("%Y%m%d")
        except ValueError:
            return None
    return None


def _to_float(value: Any) -> float:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 0.0
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:  # noqa: BLE001
        return 0.0


def _validate_frame(df: pd.DataFrame) -> Tuple[str, str]:
    if df is None or df.empty:
        return "error", "UPSTREAM_EMPTY"
    for col in REQUIRED_COLS:
        if col not in df.columns:
            return "error", "UPSTREAM_SCHEMA_DRIFT"
    return "ok", ""


def _build_meta(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    quality_status: str,
    source_raw: str,
    run_id: str,
) -> Dict[str, Any]:
    return {
        "schema_name": "csindex_daily",
        "schema_version": "1.0.0",
        "task_id": "collect_csindex_index_daily",
        "run_id": run_id,
        "data_layer": "L1",
        "generated_at": _utc_now_iso(),
        "trade_date": end_date,
        "symbol": symbol,
        "date_range": {"start_date": start_date, "end_date": end_date},
        "source_tools": ["ak.stock_zh_index_hist_csindex"],
        "lineage_refs": [f"akshare:stock_zh_index_hist_csindex:{symbol}:{start_date}:{end_date}"],
        "quality_status": quality_status,
        "unit_map": {
            "volume": "手(依上游口径)",
            "amount": "元(依上游口径)",
        },
    }


def _normalize_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    frame = df.copy()
    frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce")
    frame = frame.dropna(subset=["日期"]).sort_values("日期").drop_duplicates(subset=["日期"], keep="last")
    frame["日期"] = frame["日期"].dt.strftime(DATE_FORMAT)
    for _, row in frame.iterrows():
        out.append(
            {
                "date": str(row.get("日期", "")),
                "open": _to_float(row.get("开盘")),
                "high": _to_float(row.get("最高")),
                "low": _to_float(row.get("最低")),
                "close": _to_float(row.get("收盘")),
                "volume": _to_float(row.get("成交量")),
                "amount": _to_float(row.get("成交额")),
                "change_percent": _to_float(row.get("涨跌幅")),
            }
        )
    return out


def fetch_csindex_index_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    task_id: str = "collect_csindex_index_daily",
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    started = perf_counter()
    run_id = run_id or str(uuid4())
    source_raw = "akshare.stock_zh_index_hist_csindex"

    start_norm = _normalize_input_date(start_date)
    end_norm = _normalize_input_date(end_date)
    if not symbol or not start_norm or not end_norm:
        resp = {
            "success": False,
            "message": "symbol/start_date/end_date 参数无效，日期应为 YYYYMMDD 或 YYYY-MM-DD",
            "failure_code": "INVALID_PARAM",
            "data": [],
            "count": 0,
            "quality_status": "error",
            "degraded_reason": "INVALID_PARAM",
            "attempts": [{"source_id": "akshare", "source_raw": source_raw, "status": "failed", "failure_code": "INVALID_PARAM"}],
            "task_id": task_id,
            "run_id": run_id,
            "_meta": _build_meta(
                symbol=symbol,
                start_date=str(start_date),
                end_date=str(end_date),
                quality_status="error",
                source_raw=source_raw,
                run_id=run_id,
            ),
        }
        resp = with_source_meta(resp, source_raw=source_raw, source_stage="primary", source_interface="stock_zh_index_hist_csindex")
        resp["elapsed_ms"] = int((perf_counter() - started) * 1000)
        return resp

    if not AKSHARE_AVAILABLE:
        resp = {
            "success": False,
            "message": "akshare 未安装，无法采集中证指数日频数据",
            "failure_code": "DEPENDENCY_MISSING",
            "data": [],
            "count": 0,
            "quality_status": "error",
            "degraded_reason": "DEPENDENCY_MISSING",
            "attempts": [{"source_id": "akshare", "source_raw": source_raw, "status": "failed", "failure_code": "DEPENDENCY_MISSING"}],
            "task_id": task_id,
            "run_id": run_id,
            "_meta": _build_meta(
                symbol=symbol,
                start_date=start_norm,
                end_date=end_norm,
                quality_status="error",
                source_raw=source_raw,
                run_id=run_id,
            ),
        }
        resp = with_source_meta(resp, source_raw=source_raw, source_stage="primary", source_interface="stock_zh_index_hist_csindex")
        resp["elapsed_ms"] = int((perf_counter() - started) * 1000)
        return resp

    try:
        df = ak.stock_zh_index_hist_csindex(
            symbol=symbol,
            start_date=start_norm,
            end_date=end_norm,
        )
    except Exception as exc:  # noqa: BLE001
        resp = {
            "success": False,
            "message": f"中证指数采集失败: {exc}",
            "failure_code": "UPSTREAM_ERROR",
            "data": [],
            "count": 0,
            "quality_status": "error",
            "degraded_reason": "UPSTREAM_ERROR",
            "attempts": [{"source_id": "akshare", "source_raw": source_raw, "status": "failed", "failure_code": "UPSTREAM_ERROR"}],
            "task_id": task_id,
            "run_id": run_id,
            "_meta": _build_meta(
                symbol=symbol,
                start_date=start_norm,
                end_date=end_norm,
                quality_status="error",
                source_raw=source_raw,
                run_id=run_id,
            ),
        }
        resp = with_source_meta(resp, source_raw=source_raw, source_stage="primary", source_interface="stock_zh_index_hist_csindex")
        resp["elapsed_ms"] = int((perf_counter() - started) * 1000)
        return resp

    quality_status, failure_code = _validate_frame(df)
    if quality_status == "error":
        resp = {
            "success": False,
            "message": "中证指数数据为空或字段漂移",
            "failure_code": failure_code,
            "data": [],
            "count": 0,
            "quality_status": "error",
            "degraded_reason": failure_code,
            "attempts": [{"source_id": "akshare", "source_raw": source_raw, "status": "failed", "failure_code": failure_code}],
            "task_id": task_id,
            "run_id": run_id,
            "_meta": _build_meta(
                symbol=symbol,
                start_date=start_norm,
                end_date=end_norm,
                quality_status="error",
                source_raw=source_raw,
                run_id=run_id,
            ),
        }
        resp = with_source_meta(resp, source_raw=source_raw, source_stage="primary", source_interface="stock_zh_index_hist_csindex")
        resp["elapsed_ms"] = int((perf_counter() - started) * 1000)
        return resp

    records = _normalize_records(df)
    degraded_reason = ""
    if not records:
        quality_status = "error"
        degraded_reason = "NORMALIZE_FAILED"

    success = bool(records)
    resp = {
        "success": success,
        "message": "Successfully fetched CSIndex daily data" if success else "中证指数标准化失败",
        "failure_code": "" if success else "NORMALIZE_FAILED",
        "data": records,
        "count": len(records),
        "quality_status": "ok" if success else quality_status,
        "degraded_reason": degraded_reason,
        "attempts": [
            {
                "source_id": "akshare",
                "source_raw": source_raw,
                "status": "ok" if success else "failed",
                "failure_code": "" if success else "NORMALIZE_FAILED",
            }
        ],
        "task_id": task_id,
        "run_id": run_id,
        "_meta": _build_meta(
            symbol=symbol,
            start_date=start_norm,
            end_date=end_norm,
            quality_status="ok" if success else quality_status,
            source_raw=source_raw,
            run_id=run_id,
        ),
    }
    resp = with_source_meta(resp, source_raw=source_raw, source_stage="primary", source_interface="stock_zh_index_hist_csindex")
    resp["elapsed_ms"] = int((perf_counter() - started) * 1000)
    return resp


def tool_fetch_csindex_index_daily(
    symbol: str = "000300",
    start_date: str = "",
    end_date: str = "",
    task_id: str = "collect_csindex_index_daily",
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """OpenClaw 工具：获取中证指数日频数据。"""
    return fetch_csindex_index_daily(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        task_id=task_id,
        run_id=run_id,
    )
