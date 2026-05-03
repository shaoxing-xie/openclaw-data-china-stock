from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from plugins.data_collection.technical_indicators.alignment import apply_alignment
from plugins.data_collection.technical_indicators.engine import TechnicalIndicatorEngine
from plugins.data_collection.technical_indicators.indicators import calculate_p0_indicators, factor_hooks
from plugins.data_collection.technical_indicators.validator import validate_min_rows, validate_ohlcv
from plugins.merged.fetch_market_data import tool_fetch_market_data


def tool_calculate_technical_indicators(
    asset_code: str,
    asset_type: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    indicators: Dict[str, Any] | None = None,
    return_mode: str = "standalone",
    use_cache: bool = True,
    engine_preference: str = "auto",
    output_schema_version: str = "v1",
    alignment: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    try:
        fetch_res = tool_fetch_market_data(
            asset_type=asset_type,
            asset_code=asset_code,
            view="historical",
            period=period,
            start_date=start_date or None,
            end_date=end_date or None,
            use_cache=use_cache,
        )
        if not fetch_res.get("success"):
            return {
                "success": False,
                "engine": None,
                "data": None,
                "meta": {},
                "warnings": [],
                "error": {"error_code": "UPSTREAM_FETCH_FAILED", "message": fetch_res.get("message", "历史数据获取失败")},
            }

        raw_df = _extract_dataframe(fetch_res.get("data"))
        if raw_df.empty:
            return {
                "success": False,
                "engine": None,
                "data": None,
                "meta": {},
                "warnings": [],
                "error": {"error_code": "UPSTREAM_EMPTY_DATA", "message": "历史数据为空，无法计算技术指标"},
            }
        ok, missing = validate_ohlcv(raw_df)
        if not ok:
            return {
                "success": False,
                "engine": None,
                "data": None,
                "meta": {},
                "warnings": [],
                "error": {
                    "error_code": "VALIDATION_ERROR",
                    "message": "输入数据缺少必需字段",
                    "missing_fields": missing,
                },
            }
        if not validate_min_rows(raw_df, min_rows=35):
            return {
                "success": False,
                "engine": None,
                "data": None,
                "meta": {},
                "warnings": [],
                "error": {"error_code": "VALIDATION_ERROR", "message": "数据长度不足，至少需要 35 条记录"},
            }

        sel = TechnicalIndicatorEngine.select(engine_preference=engine_preference)
        catalog_engine_order = TechnicalIndicatorEngine.catalog_auto_engine_order()
        df = calculate_p0_indicators(raw_df, sel.name, sel.talib, sel.pandas_ta)
        alignment_applied = apply_alignment(df, alignment=alignment)
        data = _to_output(df, return_mode=return_mode)
        if isinstance(data, list):
            latest = data[-1] if data else {}
        elif isinstance(data, dict):
            latest = data.get("latest") if isinstance(data.get("latest"), dict) else {}
        else:
            latest = {}

        return {
            "success": True,
            "engine": sel.name,
            "data": data,
            "meta": {
                "asset": {"asset_code": asset_code, "asset_type": asset_type},
                "period": period,
                "rows": len(df.index),
                "output_schema_version": output_schema_version or "v1",
                "calculated_indicators": _p0_p1_indicator_list(),
                "alignment_applied": alignment_applied,
                "factor_hooks": factor_hooks(latest if isinstance(latest, dict) else {}),
                "catalog_engine_order": catalog_engine_order,
                "catalog_dataset_id": "technical_indicators",
            },
            "warnings": _engine_warning(sel.name, engine_preference),
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "engine": None,
            "data": None,
            "meta": {},
            "warnings": [],
            "error": {"error_code": "RUNTIME_ERROR", "message": str(e)},
        }


def _extract_dataframe(data: Any) -> pd.DataFrame:
    if isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, dict):
        if isinstance(data.get("rows"), list):
            df = pd.DataFrame(data["rows"])
        elif isinstance(data.get("data"), list):
            df = pd.DataFrame(data["data"])
        elif isinstance(data.get("klines"), list):
            df = pd.DataFrame(data["klines"])
        else:
            df = pd.DataFrame([data])
    else:
        df = pd.DataFrame()

    rename_map = {
        "date": "date",
        "日期": "date",
        "open": "open",
        "开盘": "open",
        "high": "high",
        "最高": "high",
        "low": "low",
        "最低": "low",
        "close": "close",
        "收盘": "close",
        "volume": "volume",
        "成交量": "volume",
    }
    for k, v in list(rename_map.items()):
        if k in df.columns and v not in df.columns:
            df[v] = df[k]
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.reset_index(drop=True)


def _to_output(df: pd.DataFrame, return_mode: str) -> Any:
    clean_df = df.replace({np.nan: None})
    mode = (return_mode or "standalone").strip().lower()
    if mode == "append":
        return clean_df.to_dict(orient="records")

    # standalone: latest snapshot + compact series payload
    latest = clean_df.iloc[-1].to_dict()
    return {
        "latest": latest,
        "series": clean_df.to_dict(orient="records"),
    }


def _engine_warning(engine_name: str, preference: str) -> List[str]:
    pref = (preference or "auto").strip().lower()
    if pref == "auto" and engine_name == "pandas_ta":
        return ["TA-Lib 不可用，已自动降级到 pandas-ta"]
    if pref == "auto" and engine_name == "builtin":
        return ["TA-Lib 与 pandas-ta 均不可用，已使用内置计算实现（精度可能与 TA-Lib 存在差异）"]
    return []


def _p0_p1_indicator_list() -> List[str]:
    return [
        # P0
        "SMA",
        "EMA",
        "MACD",
        "ADX",
        "WMA",
        "DEMA",
        "TEMA",
        "SAR",
        "RSI",
        "KDJ",
        "STOCH",
        "STOCHF",
        "CCI",
        "WILLR",
        "MOM",
        "ROC",
        "BBANDS",
        "ATR",
        "NATR",
        # P1
        "OBV",
        "MFI",
        "AD",
        "ADOSC",
        "TRIMA",
        "KAMA",
        "APO",
        "PPO",
        "DX",
        "HT_TRENDLINE",
        # P2 pattern recognition (20)
        "CDLDOJI",
        "CDLDRAGONFLYDOJI",
        "CDLGRAVESTONEDOJI",
        "CDLHAMMER",
        "CDLHANGINGMAN",
        "CDLINVERTEDHAMMER",
        "CDLSHOOTINGSTAR",
        "CDLENGULFING",
        "CDLPIERCING",
        "CDLDARKCLOUDCOVER",
        "CDLMORNINGSTAR",
        "CDLEVENINGSTAR",
        "CDL3WHITESOLDIERS",
        "CDL3BLACKCROWS",
        "CDLHARAMI",
        "CDLHARAMICROSS",
        "CDLSPINNINGTOP",
        "CDLMARUBOZU",
        "CDLTAKURI",
        "CDLRISEFALL3METHODS",
        # P2 statistics / others (6)
        "BETA",
        "CORREL",
        "LINEARREG",
        "LINEARREG_SLOPE",
        "LINEARREG_ANGLE",
        "STDDEV",
        # P2 volatility supplement (3)
        "TRANGE",
        "HT_DCPERIOD",
        "HT_DCPHASE",
    ]

