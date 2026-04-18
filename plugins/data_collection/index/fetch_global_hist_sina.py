"""
Backward-compatible global index history tool.

This module restores the legacy import path:
`plugins.data_collection.index.fetch_global_hist_sina`
which is still referenced by assistant-side workflows.

数据源顺序（与 ``fetch_global.fetch_global_index_spot`` 中 yfinance/FMP/新浪 链一致，历史侧另行组合）：

- **美股日线（DJI/SPX/IXIC）**：``yfinance`` → ``ak.index_global_hist_em``（东财）；不试新浪 hist（cons 无美股键）。
- **其它指数**：``ak.index_global_hist_sina``（新浪键名）→ 失败则返回错误（不走 yfinance）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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
# 与 yfinance 符号对齐；新浪 global_hist 入参需用 index_global_sina_symbol_map 中的中文名（见 akshare.index.cons）。
_SYMBOL_ALIASES = {
    "^DJI": "DJI",
    "^IXIC": "IXIC",
    "^GSPC": "SPX",
    "^N225": "N225",
    "^HSI": "HSI",
    "^FTSE": "UKX",
    "^GDAXI": "DAX",
    "^STOXX50E": "SX5E",
    "^KS11": "KOSPI",
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
    # 英国富时100：英国富时100指数 为新浪表内稳定名称
    "UKX": ["英国富时100指数", "UKX"],
    # 德国DAX：必须用 cons 中全名「德国DAX 30种股价指数」，旧候选「德国DAX指数」会报不存在
    "DAX": ["德国DAX 30种股价指数", "DAX", "德国DAX指数", "德国DAX"],
    "CAC": ["CAC", "法国CAC40"],
    # 欧洲斯托克50：欧洲Stoxx50指数（新浪）；SX5E 为内部代码备选
    "SX5E": ["欧洲Stoxx50指数", "SX5E"],
    # 韩国综合：首尔综合指数（新浪 map）；与 ^KS11 / EM 代码 KS11 对齐
    "KOSPI": ["首尔综合指数", "KOSPI"],
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


# 新浪 cons.index_global_sina_symbol_map 不含美股三大；hist 需走东财或 yfinance。
_EM_HIST_NAME_BY_NORMALIZED: Dict[str, str] = {
    "DJI": "道琼斯",
    "SPX": "标普500",
    "IXIC": "纳斯达克",
}
_YF_SYMBOL_BY_NORMALIZED: Dict[str, str] = {
    "DJI": "^DJI",
    "SPX": "^GSPC",
    "IXIC": "^IXIC",
}


def _em_hist_df_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """东财 index_global_hist_em 列为中文，转为与新浪 hist 一致的 date/close 等。"""
    if df is None or df.empty:
        return df
    col_date = next((c for c in ("日期", "date") if c in df.columns), None)
    col_close = next((c for c in ("最新价", "close", "Close") if c in df.columns), None)
    if not col_date or not col_close:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[col_date], errors="coerce").dt.strftime("%Y-%m-%d"),
            "open": pd.to_numeric(df.get("今开", df.get("open")), errors="coerce"),
            "high": pd.to_numeric(df.get("最高", df.get("high")), errors="coerce"),
            "low": pd.to_numeric(df.get("最低", df.get("low")), errors="coerce"),
            "close": pd.to_numeric(df[col_close], errors="coerce"),
            "volume": pd.to_numeric(df.get("volume"), errors="coerce"),
        }
    )
    out = out.dropna(subset=["close"])
    return out.sort_values("date")


def _yf_hist_to_records(normalized: str) -> Optional[List[Dict[str, Any]]]:
    sym = _YF_SYMBOL_BY_NORMALIZED.get(normalized)
    if not sym:
        return None
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        t = yf.Ticker(sym)
        hist = t.history(period="12d")
    except Exception:
        return None
    if hist is None or hist.empty or len(hist) < 2:
        return None
    out: list[dict[str, Any]] = []
    for idx in hist.index:
        try:
            close = float(hist["Close"].loc[idx])
        except Exception:
            continue
        out.append(
            {
                "date": str(idx.date()),
                "open": float(hist["Open"].loc[idx]) if "Open" in hist.columns else None,
                "high": float(hist["High"].loc[idx]) if "High" in hist.columns else None,
                "low": float(hist["Low"].loc[idx]) if "Low" in hist.columns else None,
                "close": close,
                "volume": float(hist["Volume"].loc[idx]) if "Volume" in hist.columns else None,
            }
        )
    return out if len(out) >= 2 else None


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

    数据源优先级（手工/逻辑约定）：

    - **美股日线 DJI/SPX/IXIC**：与 ``fetch_global.py`` 现货一致——**yfinance → 东财**；新浪 cons 无美股键，不试新浪 hist。
    - **其它地区**：**新浪 global_hist →（仅上述三标的才会再走东财/yfinance，已由上方分支处理）**。
    """
    normalized = _normalize_symbol(symbol)
    rows = max(1, int(limit or 1))
    last_error: Optional[str] = None

    # ---------- 美股三大：日线优先 yfinance，其次东财（与现货主源 yfinance 对齐） ----------
    if normalized in _EM_HIST_NAME_BY_NORMALIZED:
        yf_recs = _yf_hist_to_records(normalized)
        if yf_recs and len(yf_recs) >= 2:
            tail = yf_recs[-rows:] if len(yf_recs) > rows else yf_recs
            return {
                "success": True,
                "count": len(tail),
                "data": tail,
                "source": "yfinance",
            }
        df_us: Optional[pd.DataFrame] = None
        source_us = "akshare.index_global_hist_em"
        if hasattr(ak, "index_global_hist_em"):
            try:
                raw_em = ak.index_global_hist_em(symbol=_EM_HIST_NAME_BY_NORMALIZED[normalized])
                df_us = _em_hist_df_to_canonical(raw_em)
                if isinstance(df_us, pd.DataFrame) and not df_us.empty:
                    source_us = "akshare.index_global_hist_em"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                df_us = None
        if isinstance(df_us, pd.DataFrame) and not df_us.empty:
            if "date" in df_us.columns:
                df_us = df_us.sort_values("date")
            if len(df_us) > rows:
                df_us = df_us.tail(rows)
            recs = _to_records(df_us)
            return {
                "success": True,
                "count": len(recs),
                "data": recs,
                "source": source_us,
            }
        result: Dict[str, Any] = {
            "success": False,
            "count": 0,
            "data": [],
            "source": "yfinance",
        }
        if last_error:
            result["message"] = last_error
        return result

    # ---------- 非美股：优先新浪 global_hist ----------
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
