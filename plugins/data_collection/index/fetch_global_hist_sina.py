"""
Backward-compatible global index history tool.

This module restores the legacy import path:
`plugins.data_collection.index.fetch_global_hist_sina`
which is still referenced by assistant-side workflows.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import akshare as ak
import pandas as pd

# Common aliases used by assistant/report logic.
_GLOBAL_NAME_TO_SYMBOL = {
    "道琼斯": "DJI",
    "纳斯达克": "IXIC",
    "标普500": "SPX",
    "日经225": "N225",
    "恒生指数": "HSI",
    "英国富时100指数": "UKX",
    "德国DAX": "DAX",
    "法国CAC40": "CAC",
}

# Common ticker aliases observed in assistant workflows.
_SYMBOL_ALIASES = {
    "^DJI": "DJI",
    "^IXIC": "IXIC",
    "^GSPC": "SPX",
    "^N225": "N225",
    "^HSI": "HSI",
    "DJIA": "DJI",
    "NASDAQ": "IXIC",
    "SP500": "SPX",
}

_AK_ALT_SYMBOLS = {
    "DJI": ["DJI", "道琼斯指数", "道琼斯"],
    "IXIC": ["IXIC", "纳斯达克综合指数", "纳斯达克"],
    "SPX": ["SPX", "标普500指数", "标普500"],
    "N225": ["N225", "日经225指数", "日经225"],
    "HSI": ["HSI", "恒生指数"],
    "UKX": ["UKX", "英国富时100指数"],
    "DAX": ["DAX", "德国DAX"],
    "CAC": ["CAC", "法国CAC40"],
}


def _load_global_name_table() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return (name->symbol, symbol->name) mappings."""
    symbol_to_name = {v: k for k, v in _GLOBAL_NAME_TO_SYMBOL.items()}
    return dict(_GLOBAL_NAME_TO_SYMBOL), symbol_to_name


def _normalize_symbol(symbol: str) -> str:
    s = str(symbol or "").strip()
    if not s:
        raise KeyError("symbol is required")

    name_to_symbol, _ = _load_global_name_table()
    if s in name_to_symbol:
        return name_to_symbol[s]

    upper = s.upper()
    if upper in _SYMBOL_ALIASES:
        return _SYMBOL_ALIASES[upper]
    if upper in name_to_symbol.values():
        return upper
    if upper.startswith("^"):
        naked = upper[1:]
        if naked in name_to_symbol.values():
            return naked

    raise KeyError(f"unknown global index symbol: {symbol}")


def _to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        out.append(
            {
                "date": str(row.get("date") or ""),
                "open": float(row.get("open")) if pd.notna(row.get("open")) else None,
                "high": float(row.get("high")) if pd.notna(row.get("high")) else None,
                "low": float(row.get("low")) if pd.notna(row.get("low")) else None,
                "close": float(row.get("close")) if pd.notna(row.get("close")) else None,
                "volume": float(row.get("volume")) if pd.notna(row.get("volume")) else None,
            }
        )
    return out


def fetch_global_index_hist_sina(symbol: str, limit: int = 60) -> Dict[str, Any]:
    """
    Legacy-compatible global index history fetcher.

    Args:
        symbol: Global index symbol or known Chinese name.
        limit: Number of latest rows to return.
    """
    normalized = _normalize_symbol(symbol)
    rows = max(1, int(limit or 1))

    # Keep old behavior preference: try index_global_hist_sina first.
    if hasattr(ak, "index_global_hist_sina"):
        api = ak.index_global_hist_sina
        source = "akshare.index_global_hist_sina"
    elif hasattr(ak, "index_global_hist_em"):
        api = ak.index_global_hist_em
        source = "akshare.index_global_hist_em"
    else:
        raise RuntimeError("akshare does not provide global index history API")

    candidates = _AK_ALT_SYMBOLS.get(normalized, [normalized])
    df: Optional[pd.DataFrame] = None
    last_error: Optional[str] = None
    for cand in candidates:
        try:
            maybe_df = api(symbol=cand)
            if isinstance(maybe_df, pd.DataFrame) and not maybe_df.empty:
                df = maybe_df
                break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue

    if not isinstance(df, pd.DataFrame) or df.empty:
        result: Dict[str, Any] = {"success": False, "count": 0, "data": [], "source": source}
        if last_error:
            result["message"] = last_error
        return result

    if "date" in df.columns:
        df = df.sort_values("date")
    if len(df) > rows:
        df = df.tail(rows)

    records = _to_records(df)
    return {
        "success": True,
        "count": len(records),
        "data": records,
        "source": source,
    }


def tool_fetch_global_index_hist_sina(symbol: str, limit: int = 60) -> Dict[str, Any]:
    """OpenClaw tool entry for legacy workflow compatibility."""
    return fetch_global_index_hist_sina(symbol=symbol, limit=limit)
