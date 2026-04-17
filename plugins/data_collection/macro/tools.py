"""Macro data tools for China macro analyst."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency at runtime
    pd = None

from .akshare_wrapper import AKShareMacroWrapper
from .constants import DEFAULT_DQ_POLICY, MACRO_DATASET_MAP


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_records(data: Any) -> List[Dict[str, Any]]:
    if pd is not None and isinstance(data, pd.DataFrame):
        df = data.copy()
        df = df.where(pd.notna(df), None)
        return df.to_dict(orient="records")
    if isinstance(data, list):
        return [r if isinstance(r, dict) else {"value": r} for r in data]
    if isinstance(data, dict):
        return [data]
    return []


def _pick_latest_date(records: List[Dict[str, Any]]) -> Optional[str]:
    if not records:
        return None
    candidates: List[str] = []
    date_keys = (
        "date",
        "日期",
        "时间",
        "月份",
        "month",
        "period",
        "统计时间",
        "time",
    )
    for row in records:
        for key in date_keys:
            val = row.get(key)
            if val is not None and str(val).strip():
                candidates.append(str(val).strip())
                break
    return candidates[-1] if candidates else None


def _sort_records_by_date(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not records:
        return records

    def _row_date(row: Dict[str, Any]) -> datetime:
        date_keys = ("date", "日期", "时间", "月份", "month", "period", "统计时间", "time")
        for key in date_keys:
            val = row.get(key)
            dt = _parse_date_like(str(val)) if val is not None else None
            if dt is not None:
                return dt
        return datetime.min

    return sorted(records, key=_row_date)


def _parse_date_like(date_text: Optional[str]) -> Optional[datetime]:
    if not date_text:
        return None
    s = date_text.strip().replace("/", "-").replace(".", "-")
    fmts = (
        "%Y-%m-%d",
        "%Y-%m",
        "%Y%m%d",
        "%Y%m",
        "%Y年%m月",
        "%Y年%m月份",
        "%Y年%m月%d日",
    )
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _staleness_days(as_of: Optional[str]) -> Optional[int]:
    dt = _parse_date_like(as_of)
    if not dt:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return max((now - dt).days, 0)


def _data_quality(staleness: Optional[int]) -> Dict[str, Any]:
    if staleness is None:
        return {
            "status": "unknown",
            "policy": DEFAULT_DQ_POLICY,
            "reason": "as_of_unparsable_or_missing",
        }
    if staleness > DEFAULT_DQ_POLICY["staleness_days_error"]:
        status = "error"
    elif staleness > DEFAULT_DQ_POLICY["staleness_days_warn"]:
        status = "warn"
    else:
        status = "ok"
    return {"status": status, "policy": DEFAULT_DQ_POLICY}


def tool_fetch_macro_data(
    dataset: str,
    latest_only: bool = False,
    lookback: int = 24,
    frequency: str = "monthly",
) -> Dict[str, Any]:
    """Unified macro tool entry.

    Args:
        dataset: one of MACRO_DATASET_MAP keys
        latest_only: whether only return latest record
        lookback: maximum record count when not latest_only
        frequency: informational only; returned in meta
    """
    key = (dataset or "").strip().lower()
    if key not in MACRO_DATASET_MAP:
        return {
            "success": False,
            "data": None,
            "error": {
                "error_code": "VALIDATION_ERROR",
                "message": f"unsupported dataset: {dataset}",
                "supported_datasets": sorted(MACRO_DATASET_MAP.keys()),
            },
        }

    func_name, source, unit = MACRO_DATASET_MAP[key]
    wrapper = AKShareMacroWrapper()
    fetched = wrapper.fetch(func_name)
    if not fetched.get("success"):
        return {
            "success": False,
            "data": None,
            "source": source,
            "unit": unit,
            "error": {
                "error_code": fetched.get("error_code") or "UPSTREAM_FETCH_FAILED",
                "message": fetched.get("error") or f"failed to fetch {dataset}",
                "attempt": fetched.get("attempt"),
            },
        }

    records = _to_records(fetched.get("data"))
    records = _sort_records_by_date(records)
    if latest_only and records:
        records = [records[-1]]
    elif lookback > 0 and len(records) > lookback:
        records = records[-lookback:]

    as_of = _pick_latest_date(records)
    staleness = _staleness_days(as_of)
    dq = _data_quality(staleness)
    warnings: List[str] = []
    if dq["status"] in {"warn", "error"}:
        warnings.append(f"staleness_days={staleness} exceeds policy threshold")

    return {
        "success": True,
        "data": {
            "dataset": key,
            "frequency": frequency,
            "records": records,
            "count": len(records),
        },
        "source": source,
        "source_priority": [source, "AKShare"],
        "as_of": as_of,
        "release_time": None,
        "revision_policy": "upstream_provider_revision",
        "unit": unit,
        "data_lag_days": staleness,
        "staleness_days": staleness,
        "dq_status": dq["status"],
        "dq_policy": dq["policy"],
        "generated_at": _now_iso(),
        "warnings": warnings,
        "error": None,
    }


def tool_fetch_macro_snapshot(
    scope: str = "monthly",
    include_quadrant: bool = True,
) -> Dict[str, Any]:
    """Strategy-friendly macro snapshot from key macro datasets."""
    growth = tool_fetch_macro_data("pmi_official", latest_only=True)
    inflation = tool_fetch_macro_data("cpi", latest_only=True)
    credit = tool_fetch_macro_data("social_financing", latest_only=True)

    if not (growth.get("success") and inflation.get("success") and credit.get("success")):
        return {
            "success": False,
            "data": None,
            "error": {
                "error_code": "UPSTREAM_FETCH_FAILED",
                "message": "failed to build macro snapshot from core datasets",
            },
        }

    snapshot = {
        "scope": scope,
        "growth": growth["data"]["records"][0] if growth["data"]["records"] else None,
        "inflation": inflation["data"]["records"][0] if inflation["data"]["records"] else None,
        "credit": credit["data"]["records"][0] if credit["data"]["records"] else None,
    }
    if include_quadrant:
        snapshot["quadrant"] = {
            "status": "rule_config_required",
            "message": "quadrant decision should be determined by skill config",
        }

    return {
        "success": True,
        "data": snapshot,
        "source": "multi",
        "unit": "mixed",
        "warnings": [],
        "error": None,
    }


def _compat_macro_tool(dataset: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    p = dict(params or {})
    p.update(kwargs)
    return tool_fetch_macro_data(
        dataset=dataset,
        latest_only=bool(p.get("latest_only", False)),
        lookback=int(p.get("lookback", p.get("months", 24))),
        frequency=str(p.get("frequency", "monthly")),
    )


def tool_fetch_macro_pmi(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("pmi_official", params, **kwargs)


def tool_fetch_macro_cx_pmi(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("pmi_caixin_manufacturing", params, **kwargs)


def tool_fetch_macro_cx_services_pmi(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("pmi_caixin_services", params, **kwargs)


def tool_fetch_macro_enterprise_boom(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("enterprise_boom", params, **kwargs)


def tool_fetch_macro_lpi(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("lpi", params, **kwargs)


def tool_fetch_macro_cpi(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("cpi", params, **kwargs)


def tool_fetch_macro_ppi(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("ppi", params, **kwargs)


def tool_fetch_macro_m2(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("m2_yoy", params, **kwargs)


def tool_fetch_macro_social_financing(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("social_financing", params, **kwargs)


def tool_fetch_macro_new_credit(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("new_credit", params, **kwargs)


def tool_fetch_macro_lpr(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("lpr", params, **kwargs)


def tool_fetch_macro_fx_reserves(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("fx_reserves", params, **kwargs)


def tool_fetch_macro_gdp(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("gdp", params, **kwargs)


def tool_fetch_macro_industrial_value(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("industrial_value_added", params, **kwargs)


def tool_fetch_macro_fixed_asset(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("fixed_asset_investment", params, **kwargs)


def tool_fetch_macro_leverage(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("leverage", params, **kwargs)


def tool_fetch_macro_exports_imports(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("exports_imports", params, **kwargs)


def tool_fetch_macro_trade_balance(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("trade_balance_usd", params, **kwargs)


def tool_fetch_macro_exports_yoy(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("exports_yoy_usd", params, **kwargs)


def tool_fetch_macro_unemployment(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("urban_unemployment", params, **kwargs)


def tool_fetch_macro_tax_receipts(params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    return _compat_macro_tool("tax_receipts", params, **kwargs)

