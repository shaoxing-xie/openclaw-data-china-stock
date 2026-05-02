"""
A 股资金流向统一查询（东财 / 同花顺等多源链）。

工具：tool_fetch_a_share_fund_flow
原始数据非投资建议；口径以东财/同花顺页面为准。
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import os
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except Exception:  # noqa: BLE001
    ak = None  # type: ignore[assignment]
    AKSHARE_AVAILABLE = False

try:
    import tushare as ts  # type: ignore[import]

    TUSHARE_AVAILABLE = True
except Exception:  # noqa: BLE001
    ts = None  # type: ignore[assignment]
    TUSHARE_AVAILABLE = False

try:
    from plugins.utils.proxy_env import without_proxy_env

    PROXY_ENV_AVAILABLE = True
except Exception:  # noqa: BLE001
    PROXY_ENV_AVAILABLE = False

    def without_proxy_env(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        return nullcontext()

from plugins.data_collection.utils.provider_preference import (
    normalize_provider_preference,
    reorder_provider_chain,
)
from plugins.data_collection.sentiment_common import (
    build_cache_key,
    cache_get,
    cache_set,
    infer_ttl_seconds,
    normalize_contract,
    quality_gate_records,
)

try:
    from plugins.data_collection.utils import eastmoney_fund_flow_direct as _em_http

    EM_HTTP_AVAILABLE = _em_http.em_http_available()
except Exception:  # noqa: BLE001
    _em_http = None  # type: ignore[assignment]
    EM_HTTP_AVAILABLE = False

try:
    from plugins.data_collection.utils import ths_big_deal_limited as _ths_bd

    THS_BD_LIMITED_AVAILABLE = _ths_bd.ths_big_deal_available()
except Exception:  # noqa: BLE001
    _ths_bd = None  # type: ignore[assignment]
    THS_BD_LIMITED_AVAILABLE = False

# 东财板块 / 行业下钻接口仅 今日、5日、10日（AkShare stock_sector_fund_flow_*）；d3/d20 映射为最近可用窗口
SECTOR_RANK_EM_INDICATOR = {
    "immediate": "今日",
    "d3": "5日",
    "d5": "5日",
    "d10": "10日",
    "d20": "10日",
}
SECTOR_DRILL_EM_INDICATOR = {
    "immediate": "今日",
    "d3": "5日",
    "d5": "5日",
    "d10": "10日",
    "d20": "10日",
}

QUERY_KINDS = frozenset(
    {
        "market_history",
        "sector_rank",
        "stock_rank",
        "stock_history",
        "big_deal",
        "main_force_rank",
        "sector_drill",
    }
)

# 与 manifest 中英枚举对应 → AkShare 东财 sector_type
SECTOR_TYPE_EM = {
    "industry": "行业资金流",
    "concept": "概念资金流",
    "region": "地域资金流",
}

# rank_window → 东财板块/个股排名 indicator（无「排行」后缀）
RANK_WINDOW_EM_INDICATOR = {
    "immediate": "今日",
    "d3": "3日",
    "d5": "5日",
    "d10": "10日",
    "d20": "20日",
}

# rank_window → 同花顺 symbol（个股/行业/概念资金流）
RANK_WINDOW_THS = {
    "immediate": "即时",
    "d3": "3日排行",
    "d5": "5日排行",
    "d10": "10日排行",
    "d20": "20日排行",
}

ATTEMPTS_CAP = 5
# 单次数据源调用上限（秒）；同花顺部分接口会分页拉全市场，可能接近该值；超时后尝试链下一源。
# 环境变量 AKSHARE_FUND_FLOW_ATTEMPT_TIMEOUT_SEC 可覆盖，默认 180。
_ATTEMPT_TIMEOUT_DEFAULT_SEC = 180.0
LIMIT_DEFAULT = 50
LIMIT_MAX = 200
MAX_DAYS_DEFAULT = 120
MAX_DAYS_CAP = 150
LOOKBACK_DEFAULT = 20
LOOKBACK_MAX = 120
THS_STOCK_RANK_TIMEOUT_SEC = float(os.environ.get("THS_STOCK_RANK_TIMEOUT_SEC", "120"))
THS_BIG_DEAL_TIMEOUT_SEC = float(os.environ.get("THS_BIG_DEAL_TIMEOUT_SEC", "180"))
ENABLE_EASTMONEY_FALLBACK = str(os.environ.get("FUND_FLOW_ENABLE_EASTMONEY_FALLBACK", "false")).lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THS_MARKET_PROXY_HISTORY_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "cache" / "fund_flow" / "ths_market_proxy_history.json"
)


def _clip_limit(n: int) -> int:
    return max(1, min(int(n), LIMIT_MAX))


def _infer_market(code: str) -> str:
    c = (code or "").strip()
    if len(c) != 6 or not c.isdigit():
        return "sh"
    if c.startswith(("5", "6", "9")):
        return "sh"
    if c.startswith("0") or c.startswith("3"):
        return "sz"
    return "sh"


def _get_tushare_pro():
    if not TUSHARE_AVAILABLE:
        return None
    from plugins.connectors.tushare.pro_client import get_tushare_pro as _g

    return _g()


def _tushare_ts_code(code: str, market: str) -> str:
    return f"{code}.SH" if market == "sh" else f"{code}.SZ"


def _fetch_stock_history_tushare_moneyflow(code: str, market: str, lookback_days: int) -> Optional[pd.DataFrame]:
    pro = _get_tushare_pro()
    if pro is None:
        return None
    end_dt = datetime.now()
    # 资金流是交易日序列，按自然日放大窗口，降低节假日导致的空数据概率
    start_dt = end_dt - timedelta(days=max(40, lookback_days * 4))
    ts_code = _tushare_ts_code(code, market)
    df = pro.moneyflow(
        ts_code=ts_code,
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=end_dt.strftime("%Y%m%d"),
    )
    if df is None or getattr(df, "empty", True):
        return None

    dfx = df.copy()
    if "trade_date" in dfx.columns:
        dfx["日期"] = pd.to_datetime(dfx["trade_date"], format="%Y%m%d", errors="coerce")
    else:
        dfx["日期"] = pd.NaT
    if "close" in dfx.columns:
        dfx["收盘价"] = dfx["close"]
    if "pct_chg" in dfx.columns:
        dfx["涨跌幅"] = dfx["pct_chg"]
    if "net_mf_amount" in dfx.columns:
        dfx["主力净流入-净额"] = dfx["net_mf_amount"]
    if "buy_elg_amount" in dfx.columns and "sell_elg_amount" in dfx.columns:
        dfx["超大单净流入-净额"] = dfx["buy_elg_amount"] - dfx["sell_elg_amount"]
    if "buy_lg_amount" in dfx.columns and "sell_lg_amount" in dfx.columns:
        dfx["大单净流入-净额"] = dfx["buy_lg_amount"] - dfx["sell_lg_amount"]
    if "buy_md_amount" in dfx.columns and "sell_md_amount" in dfx.columns:
        dfx["中单净流入-净额"] = dfx["buy_md_amount"] - dfx["sell_md_amount"]
    if "buy_sm_amount" in dfx.columns and "sell_sm_amount" in dfx.columns:
        dfx["小单净流入-净额"] = dfx["buy_sm_amount"] - dfx["sell_sm_amount"]
    return dfx


def _df_to_records(df: Optional[pd.DataFrame], limit: Optional[int]) -> Tuple[List[Dict[str, Any]], List[str]]:
    if df is None or getattr(df, "empty", True):
        return [], []
    if limit is not None:
        df = df.head(_clip_limit(limit)).copy()
    df = df.where(pd.notnull(df), None)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
    records = df.to_dict(orient="records")
    for row in records:
        for k, v in list(row.items()):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None
    return records, [str(c) for c in df.columns]


def _as_of_date_from_df(df: Optional[pd.DataFrame]) -> Optional[str]:
    if df is None or df.empty:
        return None
    for col in ("日期", "date", "交易日期", "时间"):
        if col in df.columns:
            try:
                v = df[col].iloc[-1]
                if hasattr(v, "isoformat"):
                    return v.isoformat()[:10]
                return str(v)[:10]
            except Exception:
                continue
    return None


def _attempt_timeout_sec() -> float:
    raw = (os.environ.get("AKSHARE_FUND_FLOW_ATTEMPT_TIMEOUT_SEC") or "").strip()
    if not raw:
        return _ATTEMPT_TIMEOUT_DEFAULT_SEC
    try:
        return max(5.0, float(raw))
    except ValueError:
        return _ATTEMPT_TIMEOUT_DEFAULT_SEC


def _call_df_with_timeout(fn: Callable[[], pd.DataFrame], timeout_sec: float) -> pd.DataFrame:
    """
    在线程中执行 AkShare 调用；超时后必须 shutdown(wait=False)，否则 Executor 退出时会
    等待仍在跑的同花顺分页请求，阻塞整条多源链（见 CPython ThreadPoolExecutor.__exit__）。
    """
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(fn)
        return fut.result(timeout=timeout_sec)
    finally:
        # 不等待：被取消等待的线程可能仍在跑 HTTP，但不得阻塞下一数据源
        ex.shutdown(wait=False, cancel_futures=False)


def _run_chain(
    preference: str,
    tagged: List[Tuple[str, Callable[[], pd.DataFrame]]],
    timeout_sec_override: Optional[float] = None,
) -> Tuple[Optional[pd.DataFrame], str, List[Dict[str, Any]], bool]:
    """
    按 provider 偏好重排后依次尝试；返回 (df, winning_tag, attempts, used_fallback)。
    """
    ordered = reorder_provider_chain(preference, tagged)
    attempts: List[Dict[str, Any]] = []
    used_fallback = False
    first_tag = ordered[0][0] if ordered else None
    timeout_sec = timeout_sec_override if timeout_sec_override is not None else _attempt_timeout_sec()
    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    with ctx:
        for tag, fn in ordered[:ATTEMPTS_CAP]:
            try:
                df = _call_df_with_timeout(fn, timeout_sec)
                if df is None or getattr(df, "empty", True):
                    attempts.append({"source": tag, "ok": False, "message": "empty"})
                    continue
                attempts.append({"source": tag, "ok": True, "message": "ok"})
                win = tag
                used_fallback = first_tag is not None and win != first_tag
                return df, win, attempts, used_fallback
            except concurrent.futures.TimeoutError:
                attempts.append(
                    {"source": tag, "ok": False, "message": f"timeout>{timeout_sec:.0f}s"}
                )
            except Exception as e:  # noqa: BLE001
                attempts.append({"source": tag, "ok": False, "message": str(e)[:220]})
    return None, "", attempts, bool(attempts)


def tool_fetch_a_share_fund_flow(
    query_kind: str,
    provider_preference: str = "auto",
    limit: int = LIMIT_DEFAULT,
    max_days: int = MAX_DAYS_DEFAULT,
    sector_type: str = "industry",
    rank_window: str = "immediate",
    stock_code: str = "",
    market: str = "",
    lookback_days: int = LOOKBACK_DEFAULT,
    sector_name: str = "",
    drill_kind: str = "industry",
    include_hist: bool = False,
    main_force_symbol: str = "全部股票",
    big_deal_stock_code: str = "",
) -> Dict[str, Any]:
    """
    统一 A 股资金流向查询。

    Args:
        query_kind: market_history | sector_rank | stock_rank | stock_history |
            big_deal | main_force_rank | sector_drill
        provider_preference: auto | eastmoney | ths
        limit: 排名类返回条数上限（默认 50，最大 200）
        max_days: market_history 截取最近交易日数量（默认 120）
        sector_type: sector_rank 用 industry | concept | region
        rank_window: immediate | d3 | d5 | d10 | d20
        stock_code: stock_history 六码；big_deal 可选过滤（列名含「代码」）
        market: sh|sz，空则按代码推断
        lookback_days: stock_history 回溯自然日窗口内截断行数
        sector_name: sector_drill 板块/行业/概念名称（与东财列表一致）
        drill_kind: industry | concept（sector_drill 的 hist 接口选择）
        include_hist: sector_drill 是否额外拉行业/概念历史资金流
        main_force_symbol: main_force_rank 传入 stock_main_fund_flow 的 symbol
        big_deal_stock_code: 大单结果按代码包含过滤（可选）

    环境变量：
        AKSHARE_FUND_FLOW_ATTEMPT_TIMEOUT_SEC：多源链上**单次** AkShare 调用超时秒数（默认 180）。
        BIG_DEAL_THS_MAX_PAGES：`big_deal` 走同花顺 HTML 分页时的最大页数（默认 30，上限 500）。
    """
    qk = (query_kind or "").strip().lower()
    cache_key = build_cache_key(
        "a_share_fund_flow_tool",
        {
            "qk": qk,
            "provider_preference": provider_preference,
            "limit": limit,
            "max_days": max_days,
            "sector_type": sector_type,
            "rank_window": rank_window,
            "stock_code": stock_code,
            "market": market,
            "lookback_days": lookback_days,
            "sector_name": sector_name,
            "drill_kind": drill_kind,
            "include_hist": include_hist,
            "main_force_symbol": main_force_symbol,
            "big_deal_stock_code": big_deal_stock_code,
        },
    )
    cached = cache_get(cache_key)
    if cached is not None:
        return normalize_contract(
            success=True,
            payload=cached,
            source=cached.get("source", "cache"),
            attempts=[{"source": "cache", "ok": True, "message": "hit"}],
            used_fallback=True,
            data_quality="cached",
            cache_hit=True,
            quality_data_type="fund_flow",
        )
    if qk not in QUERY_KINDS:
        return {
            "success": False,
            "error": f"invalid query_kind: {query_kind!r}; expected one of {sorted(QUERY_KINDS)}",
        }

    if not AKSHARE_AVAILABLE:
        return {"success": False, "error": "AkShare 未安装，无法获取资金流向数据"}

    pref = normalize_provider_preference(provider_preference)
    lim = _clip_limit(limit if limit else LIMIT_DEFAULT)
    params_echo: Dict[str, Any] = {
        "query_kind": qk,
        "provider_preference": pref,
        "limit": lim,
    }

    if qk == "market_history":
        raw = _qk_market_history(max_days, pref, params_echo)
    elif qk == "sector_rank":
        raw = _qk_sector_rank(sector_type, rank_window, pref, lim, params_echo)
    elif qk == "stock_rank":
        raw = _qk_stock_rank(rank_window, pref, lim, params_echo)
    elif qk == "stock_history":
        raw = _qk_stock_history(stock_code, market, lookback_days, params_echo)
    elif qk == "big_deal":
        raw = _qk_big_deal(big_deal_stock_code or stock_code, lim, params_echo)
    elif qk == "main_force_rank":
        raw = _qk_main_force(main_force_symbol, lim, params_echo)
    elif qk == "sector_drill":
        raw = _qk_sector_drill(sector_name, rank_window, drill_kind, include_hist, lim, params_echo)
    else:
        raw = {"success": False, "error": "unreachable"}

    wrapped = _post_process_fund_flow(raw, qk)
    if wrapped.get("success"):
        cache_set(cache_key, wrapped, infer_ttl_seconds("fund_flow"))
    return wrapped


def _safe_float(v: Any) -> float:
    try:
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s.endswith("亿"):
                return float(s[:-1]) * 1e8
            if s.endswith("万"):
                return float(s[:-1]) * 1e4
            if s.endswith("%"):
                return float(s[:-1])
            return float(s)
        return float(v)
    except Exception:
        return 0.0


def _pick_first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _load_proxy_history() -> List[Dict[str, Any]]:
    try:
        if not THS_MARKET_PROXY_HISTORY_FILE.exists():
            return []
        return json.loads(THS_MARKET_PROXY_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_proxy_history(records: List[Dict[str, Any]]) -> None:
    try:
        THS_MARKET_PROXY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        THS_MARKET_PROXY_HISTORY_FILE.write_text(json.dumps(records[-240:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("failed to persist THS market proxy history")


def _post_process_fund_flow(raw: Dict[str, Any], qk: str) -> Dict[str, Any]:
    if not raw.get("success"):
        return normalize_contract(
            success=False,
            payload={**raw, "explanation": "资金流查询失败，请根据 error_message 排查上游源。"},
            source=raw.get("source", f"a_share_fund_flow.{qk}"),
            attempts=raw.get("attempts", []),
            used_fallback=bool(raw.get("used_fallback")),
            data_quality="partial",
            cache_hit=False,
            error_code="UPSTREAM_FETCH_FAILED",
            error_message=raw.get("error") or raw.get("message"),
            quality_data_type="fund_flow",
        )

    payload = dict(raw)
    records = payload.get("records") or []
    gate = quality_gate_records(records, min_records=1, max_null_ratio=0.85)
    payload["quality_gate"] = gate
    if qk == "market_history":
        totals: List[float] = []
        for r in records:
            cands = [
                r.get("proxy_total_net"),
                r.get("主力净流入"),
                r.get("主力净流入-净额"),
                r.get("净流入"),
                r.get("今日主力净流入-净额"),
            ]
            v = 0.0
            for c in cands:
                if c is not None:
                    v = _safe_float(c)
                    break
            totals.append(v)
        payload["cumulative"] = {
            "3d": round(sum(totals[-3:]), 2) if totals else None,
            "5d": round(sum(totals[-5:]), 2) if totals else None,
            "10d": round(sum(totals[-10:]), 2) if totals else None,
        }
        payload["flow_score"] = round((_safe_float(payload["cumulative"]["5d"] or 0) / 100.0), 2)
        if "metric_semantics" not in payload:
            payload["metric_semantics"] = "proxy_from_ths_industry_aggregate"
    if qk in ("sector_rank", "stock_rank"):
        top_vals: List[float] = []
        all_vals: List[float] = []
        for r in records:
            for k, v in r.items():
                if "净流入" in str(k):
                    fv = abs(_safe_float(v))
                    all_vals.append(fv)
                    break
        top_vals = sorted(all_vals, reverse=True)[:5]
        payload["concentration_ratio"] = round(sum(top_vals) / sum(all_vals), 4) if all_vals and sum(all_vals) else 0.0
    payload["explanation"] = payload.get("explanation") or "统一输出质量字段，并补充资金趋势/集中度指标。"
    return normalize_contract(
        success=True,
        payload=payload,
        source=payload.get("source", f"a_share_fund_flow.{qk}"),
        attempts=payload.get("attempts", []),
        used_fallback=bool(payload.get("used_fallback")),
        data_quality="fresh" if gate.get("ok") else "partial",
        cache_hit=False,
        quality_data_type="fund_flow",
    )


def _qk_market_history(
    max_days: int,
    preference: str,
    params_echo: Dict[str, Any],
) -> Dict[str, Any]:
    md = int(max_days or MAX_DAYS_DEFAULT)
    md = max(1, min(md, MAX_DAYS_CAP))
    params_echo["max_days"] = md

    attempts: List[Dict[str, Any]] = []
    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    with ctx:
        try:
            df_ind = ak.stock_fund_flow_industry(symbol="即时")
            attempts.append({"source": "ths_industry", "ok": bool(df_ind is not None and not df_ind.empty), "message": "ok"})
            df_con = ak.stock_fund_flow_concept(symbol="即时")
            attempts.append({"source": "ths_concept", "ok": bool(df_con is not None and not df_con.empty), "message": "ok"})
        except Exception as e:  # noqa: BLE001
            attempts.append({"source": "ths_proxy", "ok": False, "message": str(e)[:220]})
            if ENABLE_EASTMONEY_FALLBACK and EM_HTTP_AVAILABLE and _em_http is not None:
                try:
                    df = _em_http.stock_market_fund_flow_direct()
                    attempts.append({"source": "eastmoney_http", "ok": bool(df is not None and not df.empty), "message": "ok"})
                    if df is not None and not df.empty:
                        df2 = df.tail(md)
                        records, columns = _df_to_records(df2, None)
                        return {
                            "success": True,
                            "query_kind": "market_history",
                            "provider_preference": preference,
                            "params_echo": params_echo,
                            "source": "eastmoney_http.push2his",
                            "used_fallback": True,
                            "attempts": attempts[:ATTEMPTS_CAP],
                            "columns": columns,
                            "records": records,
                            "as_of_date": _as_of_date_from_df(df2),
                        }
                except Exception as ee:  # noqa: BLE001
                    attempts.append({"source": "eastmoney_http", "ok": False, "message": str(ee)[:220]})
            return {
                "success": False,
                "query_kind": "market_history",
                "provider_preference": preference,
                "params_echo": params_echo,
                "attempts": attempts[:ATTEMPTS_CAP],
                "message": "THS 市场资金代理构建失败",
            }

    if df_ind is None or df_ind.empty:
        return {
            "success": False,
            "query_kind": "market_history",
            "provider_preference": preference,
            "params_echo": params_echo,
            "attempts": attempts[:ATTEMPTS_CAP],
            "message": "ths industry empty",
        }
    ind_net_col = _pick_first_col(df_ind, ["净额", "主力净流入", "净流入"])
    if ind_net_col is None:
        return {
            "success": False,
            "query_kind": "market_history",
            "provider_preference": preference,
            "params_echo": params_echo,
            "attempts": attempts[:ATTEMPTS_CAP],
            "message": "ths industry missing net column",
        }
    ind_nets = [_safe_float(v) for v in df_ind[ind_net_col].tolist()]
    con_nets: List[float] = []
    if df_con is not None and not df_con.empty:
        con_net_col = _pick_first_col(df_con, ["净额", "主力净流入", "净流入"])
        if con_net_col:
            con_nets = [_safe_float(v) for v in df_con[con_net_col].tolist()]
    total_net = float(sum(ind_nets) + sum(con_nets))
    positive_count = sum(1 for x in ind_nets if x > 0)
    positive_ratio = (positive_count / len(ind_nets)) if ind_nets else 0.0
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    history = _load_proxy_history()
    history = [x for x in history if x.get("date") != today]
    history.append(
        {
            "date": today,
            "proxy_total_net": total_net,
            "proxy_positive_ratio": round(positive_ratio, 4),
            "metric_semantics": "proxy_from_ths_industry_aggregate",
            "source": "ths",
        }
    )
    history = sorted(history, key=lambda x: x.get("date", ""))[-md:]
    _save_proxy_history(history)
    records = history
    columns = sorted({k for row in records for k in row.keys()}) if records else []
    return {
        "success": True,
        "query_kind": "market_history",
        "provider_preference": preference,
        "params_echo": params_echo,
        "source": "ths_proxy.market_aggregate",
        "used_fallback": False,
        "attempts": attempts[:ATTEMPTS_CAP],
        "columns": columns,
        "records": records,
        "as_of_date": today,
        "metric_semantics": "proxy_from_ths_industry_aggregate",
    }


def _qk_sector_rank(
    sector_type: str,
    rank_window: str,
    preference: str,
    limit: int,
    params_echo: Dict[str, Any],
) -> Dict[str, Any]:
    st = (sector_type or "industry").strip().lower()
    if st not in SECTOR_TYPE_EM:
        return {"success": False, "error": f"invalid sector_type: {sector_type}", "params_echo": params_echo}
    rw = (rank_window or "immediate").strip().lower()
    if rw not in RANK_WINDOW_EM_INDICATOR:
        return {"success": False, "error": f"invalid rank_window: {rank_window}", "params_echo": params_echo}

    em_indicator = SECTOR_RANK_EM_INDICATOR[rw]
    em_sector = SECTOR_TYPE_EM[st]
    ths_sym = RANK_WINDOW_THS[rw]
    params_echo.update(
        {
            "sector_type": st,
            "rank_window": rw,
            "em_indicator": em_indicator,
            "em_rank_window_note": "东财板块排名仅支持今日/5日/10日；d3/d20 已映射为 5日/10日",
        }
    )

    def em_rank() -> pd.DataFrame:
        return ak.stock_sector_fund_flow_rank(indicator=em_indicator, sector_type=em_sector)

    tagged: List[Tuple[str, Callable[[], pd.DataFrame]]] = []
    if st == "industry":
        tagged.append(("ths", lambda: ak.stock_fund_flow_industry(symbol=ths_sym)))
    elif st == "concept":
        tagged.append(("ths", lambda: ak.stock_fund_flow_concept(symbol=ths_sym)))
    if st == "region" or ENABLE_EASTMONEY_FALLBACK:
        tagged.append(("eastmoney", em_rank))
    # region: 仅东财

    tagged = reorder_provider_chain(preference, tagged)
    df, win, attempts, used_fb = _run_chain(preference, tagged)
    if df is None or df.empty:
        return {
            "success": False,
            "query_kind": "sector_rank",
            "provider_preference": preference,
            "params_echo": params_echo,
            "attempts": attempts[:ATTEMPTS_CAP],
            "message": "所有数据源均未返回有效板块排名数据",
        }
    records, columns = _df_to_records(df, limit)
    return {
        "success": True,
        "query_kind": "sector_rank",
        "provider_preference": preference,
        "params_echo": params_echo,
        "source": f"akshare:{win}",
        "used_fallback": used_fb,
        "attempts": attempts[:ATTEMPTS_CAP],
        "columns": columns,
        "records": records,
        "as_of_date": _as_of_date_from_df(df),
        "metric_semantics": "direct_from_ths" if win == "ths" else "direct_from_eastmoney",
    }


def _qk_stock_rank(
    rank_window: str,
    preference: str,
    limit: int,
    params_echo: Dict[str, Any],
) -> Dict[str, Any]:
    rw = (rank_window or "immediate").strip().lower()
    if rw not in RANK_WINDOW_EM_INDICATOR:
        return {"success": False, "error": f"invalid rank_window: {rank_window}", "params_echo": params_echo}

    ths_sym = RANK_WINDOW_THS[rw]
    em_ind = RANK_WINDOW_EM_INDICATOR[rw]
    params_echo.update({"rank_window": rw, "stock_rank_note": "THS-first；THS 大表慢，已启用分场景超时"})

    tagged: List[Tuple[str, Callable[[], pd.DataFrame]]] = [
        ("ths", lambda: ak.stock_fund_flow_individual(symbol=ths_sym)),
    ]
    if ENABLE_EASTMONEY_FALLBACK:
        tagged.append(("eastmoney", lambda: ak.stock_individual_fund_flow_rank(indicator=em_ind)))
    tagged = reorder_provider_chain(preference, tagged)
    df, win, attempts, used_fb = _run_chain(preference, tagged, timeout_sec_override=THS_STOCK_RANK_TIMEOUT_SEC)
    if df is None or df.empty:
        return {
            "success": False,
            "query_kind": "stock_rank",
            "provider_preference": preference,
            "params_echo": params_echo,
            "attempts": attempts[:ATTEMPTS_CAP],
            "message": "个股资金流排名数据源均失败",
        }
    records, columns = _df_to_records(df, limit)
    return {
        "success": True,
        "query_kind": "stock_rank",
        "provider_preference": preference,
        "params_echo": params_echo,
        "source": f"akshare:{win}",
        "used_fallback": used_fb,
        "attempts": attempts[:ATTEMPTS_CAP],
        "columns": columns,
        "records": records,
        "as_of_date": _as_of_date_from_df(df),
        "metric_semantics": "direct_from_ths" if win == "ths" else "direct_from_eastmoney",
    }


def _qk_stock_history(
    stock_code: str,
    market: str,
    lookback_days: int,
    params_echo: Dict[str, Any],
) -> Dict[str, Any]:
    code = (stock_code or "").strip()
    if len(code) != 6 or not code.isdigit():
        return {"success": False, "error": "stock_history 需要 6 位数字 stock_code", "params_echo": params_echo}
    mkt = (market or "").strip().lower() or _infer_market(code)
    if mkt not in ("sh", "sz"):
        mkt = _infer_market(code)
    lb = max(1, min(int(lookback_days or LOOKBACK_DEFAULT), LOOKBACK_MAX))
    params_echo.update({"stock_code": code, "market": mkt, "lookback_days": lb})
    params_echo["stock_history_note"] = "tushare.moneyflow 优先；失败回退 eastmoney_http -> akshare"

    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    df: Optional[pd.DataFrame] = None
    src = "tushare.moneyflow"
    attempts_h: List[Dict[str, Any]] = []
    with ctx:
        try:
            df = _fetch_stock_history_tushare_moneyflow(code, mkt, lb)
            attempts_h.append(
                {"source": "tushare.moneyflow", "ok": bool(df is not None and not df.empty), "message": "ok"}
            )
            if df is not None and not df.empty:
                src = "tushare.moneyflow"
        except Exception as e:  # noqa: BLE001
            attempts_h.append({"source": "tushare.moneyflow", "ok": False, "message": str(e)[:220]})
        if EM_HTTP_AVAILABLE and _em_http is not None:
            if df is None or getattr(df, "empty", True):
                try:
                    df = _em_http.stock_individual_fund_flow_direct(code, mkt)
                    attempts_h.append(
                        {"source": "eastmoney_http", "ok": bool(df is not None and not df.empty), "message": "ok"}
                    )
                    if df is not None and not df.empty:
                        src = "eastmoney_http.push2his"
                except Exception as e:  # noqa: BLE001
                    attempts_h.append({"source": "eastmoney_http", "ok": False, "message": str(e)[:220]})
        if df is None or getattr(df, "empty", True):
            try:
                df = ak.stock_individual_fund_flow(stock=code, market=mkt)
                attempts_h.append({"source": "akshare", "ok": bool(df is not None and not df.empty), "message": "ok"})
                src = "akshare.stock_individual_fund_flow"
            except Exception as e:  # noqa: BLE001
                attempts_h.append({"source": "akshare", "ok": False, "message": str(e)[:220]})
                return {
                    "success": False,
                    "query_kind": "stock_history",
                    "error": str(e),
                    "params_echo": params_echo,
                    "attempts": attempts_h[:ATTEMPTS_CAP],
                }
    if df is None or df.empty:
        return {"success": False, "query_kind": "stock_history", "message": "empty", "params_echo": params_echo}
    # 按日期列截取最近 lb 行（若存在日期列）
    dfc = df.copy()
    date_col = None
    for c in ("日期", "date"):
        if c in dfc.columns:
            date_col = c
            break
    if date_col:
        try:
            dfc[date_col] = pd.to_datetime(dfc[date_col])
            dfc = dfc.sort_values(date_col).tail(lb)
        except Exception:
            dfc = dfc.tail(lb)
    else:
        dfc = dfc.tail(lb)

    records, columns = _df_to_records(dfc, None)
    used_fb = src != "tushare.moneyflow"
    return {
        "success": True,
        "query_kind": "stock_history",
        "params_echo": params_echo,
        "source": src,
        "used_fallback": used_fb,
        "attempts": attempts_h[:ATTEMPTS_CAP],
        "columns": columns,
        "records": records,
        "as_of_date": _as_of_date_from_df(dfc),
    }


def _filter_big_deal_dataframe(df: pd.DataFrame, filter_code: str) -> pd.DataFrame:
    fc = (filter_code or "").strip()
    if not fc or len(fc) < 6:
        return df
    for c in df.columns:
        if "代码" in str(c):
            mask = df[c].astype(str).str.contains(fc, na=False)
            return df[mask]
    return df


def _qk_big_deal(
    filter_code: str,
    limit: int,
    params_echo: Dict[str, Any],
) -> Dict[str, Any]:
    fc_raw = (filter_code or "").strip()
    params_echo["big_deal_filter_code"] = fc_raw
    params_echo["big_deal_ths_max_pages_hint"] = (
        os.environ.get("BIG_DEAL_THS_MAX_PAGES") or "30"
    ) + "（同花顺分页上限，可改环境变量）"

    lim = _clip_limit(limit if limit else LIMIT_DEFAULT)
    want = max(lim * 3, 200)
    attempts: List[Dict[str, Any]] = []
    df: Optional[pd.DataFrame] = None
    src = ""
    interpretation = ""

    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    with ctx:
        if THS_BD_LIMITED_AVAILABLE and _ths_bd is not None:
            try:
                df = _call_df_with_timeout(lambda: _ths_bd.ths_big_deal_limited(max_rows=want), THS_BIG_DEAL_TIMEOUT_SEC)
                ok = df is not None and not getattr(df, "empty", True)
                attempts.append({"source": "ths_ddzz_limited", "ok": ok, "message": "paged"})
                if ok:
                    src = "ths_html.ddzz_limited"
                    interpretation = "同花顺大单追踪 HTML 分页（受 BIG_DEAL_THS_MAX_PAGES 约束）"
            except concurrent.futures.TimeoutError:
                attempts.append({"source": "ths_ddzz_limited", "ok": False, "message": f"timeout>{THS_BIG_DEAL_TIMEOUT_SEC:.0f}s"})
            except Exception as e:  # noqa: BLE001
                attempts.append(
                    {"source": "ths_ddzz_limited", "ok": False, "message": str(e)[:220]}
                )

        if df is None or getattr(df, "empty", True):
            try:
                df = _call_df_with_timeout(lambda: ak.stock_fund_flow_big_deal(), THS_BIG_DEAL_TIMEOUT_SEC)
                ok = df is not None and not getattr(df, "empty", True)
                attempts.append({"source": "akshare_ths_full", "ok": ok, "message": "full_pages"})
                if ok:
                    src = "akshare.stock_fund_flow_big_deal"
                    interpretation = "同花顺大单全量分页（AkShare 原版，可能较慢）"
            except Exception as e:  # noqa: BLE001
                attempts.append({"source": "akshare_ths_full", "ok": False, "message": str(e)[:220]})
                return {
                    "success": False,
                    "query_kind": "big_deal",
                    "error": str(e),
                    "params_echo": params_echo,
                    "attempts": attempts[:ATTEMPTS_CAP],
                }
        if (df is None or getattr(df, "empty", True)) and ENABLE_EASTMONEY_FALLBACK and EM_HTTP_AVAILABLE and _em_http is not None:
            try:
                df = _em_http.eastmoney_big_deal_proxy_limited(want)
                ok = df is not None and not getattr(df, "empty", True)
                attempts.append({"source": "eastmoney_http_big_order_rank", "ok": ok, "message": "f72_sort_proxy"})
                if ok:
                    src = "eastmoney_http.big_order_net_inflow_rank"
                    interpretation = "东财全A股按今日大单净流入(f72)排序快照（可选兜底）"
            except Exception as e:  # noqa: BLE001
                attempts.append({"source": "eastmoney_http_big_order_rank", "ok": False, "message": str(e)[:220]})

    if df is None or df.empty:
        return {
            "success": False,
            "query_kind": "big_deal",
            "message": "empty",
            "params_echo": params_echo,
            "attempts": attempts[:ATTEMPTS_CAP],
        }

    df = _filter_big_deal_dataframe(df, fc_raw)
    params_echo["big_deal_data_interpretation"] = interpretation

    ok_idx = next((i for i, a in enumerate(attempts) if a.get("ok")), None)
    used_fb = ok_idx is not None and ok_idx > 0

    records, columns = _df_to_records(df, limit)
    return {
        "success": True,
        "query_kind": "big_deal",
        "params_echo": params_echo,
        "source": src,
        "used_fallback": used_fb,
        "attempts": attempts[:ATTEMPTS_CAP],
        "columns": columns,
        "records": records,
        "metric_semantics": "direct_from_ths" if "ths" in src else "proxy_from_eastmoney",
    }


def _qk_main_force(symbol: str, limit: int, params_echo: Dict[str, Any]) -> Dict[str, Any]:
    sym = (symbol or "全部股票").strip() or "全部股票"
    params_echo["main_force_symbol"] = sym
    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    df: Optional[pd.DataFrame] = None
    src = "akshare.stock_main_fund_flow"
    attempts_m: List[Dict[str, Any]] = []
    with ctx:
        if EM_HTTP_AVAILABLE and _em_http is not None:
            try:
                df = _em_http.stock_main_fund_flow_limited(sym, max(limit * 2, 100))
                attempts_m.append(
                    {"source": "eastmoney_http", "ok": bool(df is not None and not df.empty), "message": "ok"}
                )
                if df is not None and not df.empty:
                    src = "eastmoney_http.clist_limited"
            except Exception as e:  # noqa: BLE001
                attempts_m.append({"source": "eastmoney_http", "ok": False, "message": str(e)[:220]})
        if df is None or getattr(df, "empty", True):
            try:
                df = ak.stock_main_fund_flow(symbol=sym)
                attempts_m.append({"source": "akshare", "ok": bool(df is not None and not df.empty), "message": "ok"})
                src = "akshare.stock_main_fund_flow"
            except Exception as e:  # noqa: BLE001
                attempts_m.append({"source": "akshare", "ok": False, "message": str(e)[:220]})
                # 继续走代理降级，不立即返回

        # 主链路失败时，默认启用代理降级（THS 即时个股资金榜）
        if df is None or getattr(df, "empty", True):
            try:
                df = ak.stock_fund_flow_individual(symbol="即时")
                ok = df is not None and not getattr(df, "empty", True)
                attempts_m.append({"source": "ths_proxy_stock_rank", "ok": ok, "message": "immediate"})
                if ok:
                    src = "proxy:akshare.stock_fund_flow_individual.immediate"
            except Exception as e:  # noqa: BLE001
                attempts_m.append({"source": "ths_proxy_stock_rank", "ok": False, "message": str(e)[:220]})
    if df is None or df.empty:
        return {
            "success": False,
            "query_kind": "main_force_rank",
            "message": "empty",
            "params_echo": params_echo,
            "attempts": attempts_m[:ATTEMPTS_CAP],
        }
    records, columns = _df_to_records(df, limit)
    used_fb = src != "eastmoney_http.clist_limited"
    metric_semantics = "direct_main_force_rank"
    note: Optional[str] = None
    if src.startswith("proxy:"):
        metric_semantics = "proxy_not_equivalent_to_main_force_rank"
        note = "主力净流入榜双源失败，已降级为 THS 即时个股资金榜（代理口径）。"
    return {
        "success": True,
        "query_kind": "main_force_rank",
        "params_echo": params_echo,
        "source": src,
        "used_fallback": used_fb,
        "attempts": attempts_m[:ATTEMPTS_CAP],
        "columns": columns,
        "records": records,
        "metric_semantics": metric_semantics,
        "note": note,
    }


def _qk_sector_drill(
    sector_name: str,
    rank_window: str,
    drill_kind: str,
    include_hist: bool,
    limit: int,
    params_echo: Dict[str, Any],
) -> Dict[str, Any]:
    name = (sector_name or "").strip()
    if not name:
        return {"success": False, "error": "sector_drill 需要 sector_name", "params_echo": params_echo}
    rw = (rank_window or "immediate").strip().lower()
    em_ind = SECTOR_DRILL_EM_INDICATOR.get(rw, "今日")
    dk = (drill_kind or "industry").strip().lower()
    if dk not in ("industry", "concept"):
        return {"success": False, "error": "drill_kind 应为 industry 或 concept", "params_echo": params_echo}
    params_echo.update(
        {"sector_name": name, "indicator": em_ind, "drill_kind": dk, "include_hist": bool(include_hist)}
    )

    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    with ctx:
        try:
            df_sum = ak.stock_sector_fund_flow_summary(symbol=name, indicator=em_ind)
        except Exception as e:  # noqa: BLE001
            return {
                "success": False,
                "query_kind": "sector_drill",
                "error": str(e),
                "stage": "summary",
                "params_echo": params_echo,
            }
    out: Dict[str, Any] = {
        "success": True,
        "query_kind": "sector_drill",
        "params_echo": params_echo,
        "source": "akshare.stock_sector_fund_flow_summary",
        "used_fallback": False,
        "attempts": [{"source": "eastmoney", "ok": True, "message": "summary"}],
    }
    rec_s, col_s = _df_to_records(df_sum, limit)
    out["summary"] = {"columns": col_s, "records": rec_s}

    if include_hist:
        try:
            ctx_hist = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
            with ctx_hist:
                if dk == "industry":
                    df_h = ak.stock_sector_fund_flow_hist(symbol=name)
                    hist_src = "akshare.stock_sector_fund_flow_hist"
                else:
                    df_h = ak.stock_concept_fund_flow_hist(symbol=name)
                    hist_src = "akshare.stock_concept_fund_flow_hist"
            rec_h, col_h = _df_to_records(df_h, min(limit, 60))
            out["history"] = {"columns": col_h, "records": rec_h, "source": hist_src}
        except Exception as e:  # noqa: BLE001
            out["history_error"] = str(e)[:300]
    # 顶层仍给合并 records 便于简单消费：仅 summary
    out["columns"] = col_s
    out["records"] = rec_s
    out["as_of_date"] = _as_of_date_from_df(df_sum)
    return out
