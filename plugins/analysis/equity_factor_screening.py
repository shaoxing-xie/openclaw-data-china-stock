"""
多因子选股（震荡模板）：组合既有采集工具，单入口输出排序与质量分。

不引入新的外部数据源；行业/市值「中性化」在数据不足时显式 degraded，不静默改语义。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PLUGIN_VERSION = "0.5.3"

INDEX_UNIVERSE = {
    "hs300": "000300",
    "zz500": "000905",
    "zz1000": "000852",
}

ALLOWED_FACTORS = frozenset({"reversal_5d", "fund_flow_3d", "sector_momentum_5d"})


def _plugin_version() -> str:
    try:
        from pathlib import Path

        p = Path(__file__).resolve().parents[2] / "openclaw.plugin.json"
        if p.is_file():
            meta = json.loads(p.read_text(encoding="utf-8"))
            return str(meta.get("version") or PLUGIN_VERSION)
    except Exception:
        pass
    return PLUGIN_VERSION


def _norm_code_6(code: str) -> str:
    c = (code or "").strip()
    if "." in c:
        c = c.split(".")[0]
    if len(c) > 2 and c[:2].lower() in ("sh", "sz", "bj") and c[2:].isdigit():
        c = c[2:]
    return c[:6] if c.isdigit() and len(c) >= 6 else c.zfill(6)[:6] if c.isdigit() else c


def _config_hash(payload: Dict[str, Any]) -> str:
    keys = ("universe", "filters", "factors", "neutralize", "top_n", "regime_hint", "max_universe_size")
    sub = {k: payload.get(k) for k in keys}
    raw = json.dumps(sub, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _percentile_rank(values: List[float]) -> List[float]:
    """同长度 0–100 分位得分，NaN 置中位。"""
    s = pd.Series(values, dtype="float64")
    if s.empty:
        return []
    ok = s.notna() & np.isfinite(s)
    if not ok.any():
        return [50.0] * len(values)
    ranks = s.rank(pct=True, method="average")
    out = (ranks * 100.0).tolist()
    return [float(x) if np.isfinite(x) else 50.0 for x in out]


def _klines_from_hist(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not res.get("success"):
        return []
    data = res.get("data")
    if isinstance(data, list) and data:
        block = data[0]
    elif isinstance(data, dict):
        block = data
    else:
        return []
    klines = block.get("klines") or []
    return klines if isinstance(klines, list) else []


def _return_n_day(klines: List[Dict[str, Any]], n: int) -> Optional[float]:
    closes = [float(k.get("close") or 0) for k in klines if k.get("close") is not None]
    if len(closes) < n + 1:
        return None
    c0, c1 = closes[-1], closes[-(n + 1)]
    if c1 == 0:
        return None
    return (c0 / c1 - 1.0) * 100.0


def _extract_stock_code_from_rank_row(row: Dict[str, Any]) -> Optional[str]:
    for k, v in row.items():
        if k in ("代码", "股票代码") and v is not None:
            s = str(v).strip()
            if len(_norm_code_6(s)) == 6 and _norm_code_6(s).isdigit():
                return _norm_code_6(s)
    for k, v in row.items():
        if "代码" in str(k) and v is not None:
            s = _norm_code_6(str(v))
            if len(s) == 6 and s.isdigit():
                return s
    return None


def _extract_net_inflow(row: Dict[str, Any]) -> float:
    for k, v in row.items():
        if "净流入" in str(k):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return 0.0


def _extract_industry_name(row: Dict[str, Any]) -> str:
    for k in ("所属行业", "行业", "板块", "概念板块"):
        if k in row and row[k]:
            return str(row[k]).strip()
    for k, v in row.items():
        if "行业" in str(k) and v:
            return str(v).strip()
    return ""


def _resolve_universe(
    universe: str,
    *,
    custom_symbols: str,
    max_universe_size: int,
) -> Tuple[List[str], str, Optional[str]]:
    u = (universe or "hs300").strip().lower()
    raw_size = int(max_universe_size or 0)
    full_index_mode = u in INDEX_UNIVERSE and raw_size <= 0
    cap = max(5, min(raw_size if raw_size > 0 else 50, 1000))

    from plugins.data_collection.stock.fundamentals_extended import tool_fetch_a_share_universe
    from plugins.data_collection.stock.reference_p1 import tool_fetch_index_constituents

    if u == "custom":
        parts = [p.strip() for p in (custom_symbols or "").replace(";", ",").split(",") if p.strip()]
        codes = [_norm_code_6(p) for p in parts]
        codes = [c for c in codes if len(c) == 6 and c.isdigit()][:cap]
        if not codes:
            return [], "custom", "custom 模式需要 custom_symbols（逗号分隔六码）"
        return codes, "custom", None

    if u in INDEX_UNIVERSE:
        idx = INDEX_UNIVERSE[u]
        fetch_rows = 1000 if full_index_mode else cap
        r = tool_fetch_index_constituents(idx, max_rows=fetch_rows)
        if not r.get("success") or not r.get("data"):
            return [], f"index:{idx}", r.get("message") or "成份股获取失败"
        rows = r["data"] if isinstance(r["data"], list) else []
        codes: List[str] = []
        for row in rows:
            c = row.get("成分券代码") or row.get("品种代码") or row.get("code")
            if c:
                nc = _norm_code_6(str(c))
                if len(nc) == 6 and nc.isdigit():
                    codes.append(nc)
        if not full_index_mode:
            codes = codes[:cap]
        return codes, f"index_constituents:{idx}", None if codes else "成份股列表为空"

    if u in ("a_share", "ashare", "all_a"):
        r = tool_fetch_a_share_universe(max_rows=cap)
        if not r.get("success") or not r.get("data"):
            return [], "a_share_universe", r.get("message") or "全市场列表失败"
        codes = []
        for row in r["data"]:
            c = row.get("代码") or row.get("code")
            if c:
                nc = _norm_code_6(str(c))
                if len(nc) == 6 and nc.isdigit():
                    codes.append(nc)
        return codes[:cap], "a_share_universe", None if codes else "代码列为空"

    return [], universe, f"未知 universe={universe!r}，支持 hs300|zz500|zz1000|a_share|custom"


def tool_screen_equity_factors(
    universe: str = "hs300",
    filters: Optional[Dict[str, Any]] = None,
    factors: Optional[List[str]] = None,
    neutralize: Optional[List[str]] = None,
    top_n: int = 10,
    regime_hint: str = "oscillation",
    screening_date: Optional[str] = None,
    custom_symbols: str = "",
    max_universe_size: int = 0,
    lookback_calendar_days: int = 40,
    max_concurrent_fetch: int = 0,
    provider_preference: str = "auto",
) -> Dict[str, Any]:
    """
    多因子选股（默认震荡模板权重）。

    screening_date: 预留，当前实现使用各上游「最近可用」交易日数据。
    """
    t0 = time.perf_counter()
    filters = filters or {}
    factors = [str(f).strip() for f in (factors or ["reversal_5d", "fund_flow_3d", "sector_momentum_5d"])]
    neutralize = [str(x).strip().lower() for x in (neutralize or [])]
    unknown = [f for f in factors if f not in ALLOWED_FACTORS]
    if unknown:
        return {
            "success": False,
            "message": f"未知因子: {unknown}；允许 {sorted(ALLOWED_FACTORS)}",
            "data": None,
            "quality_score": 0.0,
            "degraded": True,
            "config_hash": "",
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "plugin_version": _plugin_version(),
        }

    codes, uni_src, uni_err = _resolve_universe(
        universe,
        custom_symbols=custom_symbols or str(filters.get("custom_symbols") or ""),
        max_universe_size=max_universe_size,
    )
    if uni_err or not codes:
        return {
            "success": False,
            "message": uni_err or "股票池为空",
            "data": None,
            "universe_source": uni_src,
            "quality_score": 0.0,
            "degraded": True,
            "config_hash": _config_hash(locals()),
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "plugin_version": _plugin_version(),
        }

    cfg_hash = _config_hash(
        {
            "universe": universe,
            "filters": filters,
            "factors": factors,
            "neutralize": neutralize,
            "top_n": top_n,
            "regime_hint": regime_hint,
            "max_universe_size": max_universe_size,
        }
    )

    from plugins.data_collection.stock.fetch_historical import tool_fetch_stock_historical

    mc = int(max_concurrent_fetch or os.environ.get("OPENCLAW_BATCH_MAX_WORKERS") or 4)
    mc = max(1, min(mc, 16))

    def _fetch_one(sym: str) -> Tuple[str, Dict[str, Any]]:
        return sym, tool_fetch_stock_historical(
            stock_code=sym,
            period="daily",
            lookback_days=lookback_calendar_days,
            use_cache=True,
        )

    hist_by_code: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=mc) as ex:
        futs = {ex.submit(_fetch_one, c): c for c in codes}
        for fut in as_completed(futs):
            sym, res = fut.result()
            hist_by_code[sym] = res

    ret5: Dict[str, Optional[float]] = {}
    ok_hist = 0
    for sym in codes:
        klines = _klines_from_hist(hist_by_code.get(sym) or {})
        r5 = _return_n_day(klines, 5)
        ret5[sym] = r5
        if r5 is not None:
            ok_hist += 1

    flow_scores: Dict[str, float] = {c: 50.0 for c in codes}
    industry_of: Dict[str, str] = {}
    if "fund_flow_3d" in factors or "sector_momentum_5d" in factors:
        from plugins.data_collection.a_share_fund_flow import tool_fetch_a_share_fund_flow

        fr = tool_fetch_a_share_fund_flow(
            query_kind="stock_rank",
            rank_window="d5",
            limit=min(200, max(50, len(codes) * 4)),
            provider_preference=provider_preference,
        )
        recs: List[Dict[str, Any]] = []
        if fr.get("success"):
            recs = list(fr.get("records") or [])
        code_to_net: Dict[str, float] = {}
        for row in recs:
            sc = _extract_stock_code_from_rank_row(row)
            if not sc or sc not in codes:
                continue
            code_to_net[sc] = _extract_net_inflow(row)
            industry_of[sc] = _extract_industry_name(row)
        nets_univ = [float(code_to_net.get(c, float("nan"))) for c in codes]
        pr_flow = _percentile_rank(nets_univ)
        for i, c in enumerate(codes):
            flow_scores[c] = float(pr_flow[i]) if i < len(pr_flow) else 50.0
        for c in codes:
            industry_of.setdefault(c, "")

    # 申万一级静态映射（东财快照导出的行业名）优先于资金流表内行业列，便于复现与中性化
    from plugins.analysis.sw_industry_mapping import industry_for_code, load_sw_level1_mapping, mapping_stats

    sw_meta: Dict[str, Any] = {}
    try:
        _, sw_meta = load_sw_level1_mapping()
    except Exception:  # noqa: BLE001
        sw_meta = {}
    hit, tot, cov = mapping_stats(codes)
    for c in codes:
        sw = industry_for_code(c)
        if sw:
            industry_of[c] = sw
        else:
            industry_of.setdefault(c, "")

    sector_chg: Dict[str, float] = {}
    if "sector_momentum_5d" in factors:
        from plugins.data_collection.sector import tool_fetch_sector_data

        sr = tool_fetch_sector_data(sector_type="industry", period="today")
        if sr.get("status") == "success":
            for row in sr.get("all_data") or []:
                nm = str(row.get("sector_name") or "").strip()
                if nm:
                    try:
                        sector_chg[nm] = float(row.get("change_percent") or 0.0)
                    except (TypeError, ValueError):
                        sector_chg[nm] = 0.0

    rev_raw = [-(ret5.get(c) or np.nan) for c in codes]
    rev_rank = _percentile_rank([float(x) if np.isfinite(x) else np.nan for x in rev_raw])

    sec_scores: List[float] = []
    for i, c in enumerate(codes):
        ind = industry_of.get(c) or ""
        ch = sector_chg.get(ind)
        if ch is None:
            sec_scores.append(np.nan)
        else:
            sec_scores.append(float(ch))

    sec_rank = _percentile_rank(sec_scores)

    degraded = False
    notes: List[str] = []
    if ok_hist < max(1, len(codes) // 2):
        degraded = True
        notes.append(f"日线成功率偏低: {ok_hist}/{len(codes)}")
    if tot > 0 and cov < 0.25 and sw_meta.get("mapping_version") not in (None, "", "empty"):
        degraded = True
        notes.append(f"申万映射覆盖率偏低: {hit}/{tot} ({cov:.0%})，行业动量可复现性下降")

    if "industry" in neutralize and industry_of:
        by_ind: Dict[str, List[int]] = {}
        for i, c in enumerate(codes):
            ind = industry_of.get(c) or "UNKNOWN"
            by_ind.setdefault(ind, []).append(i)
        if any(len(v) > 1 for v in by_ind.values()):
            arr_rev = np.array(rev_rank, dtype=float)
            for _, idxs in by_ind.items():
                if len(idxs) < 2:
                    continue
                sub = arr_rev[idxs]
                arr_rev[idxs] = sub - float(np.nanmean(sub)) + 50.0
            rev_rank = [float(x) for x in arr_rev.tolist()]
        else:
            degraded = True
            notes.append("行业中性化跳过（行业内样本不足）")

    if "market_cap" in neutralize:
        degraded = True
        notes.append("市值中性化尚未接入财务市值字段，已跳过")

    w_map = {
        "oscillation": {"reversal_5d": 0.4, "fund_flow_3d": 0.3, "sector_momentum_5d": 0.3},
        "trend": {"reversal_5d": 0.2, "fund_flow_3d": 0.4, "sector_momentum_5d": 0.4},
    }
    weights = w_map.get((regime_hint or "oscillation").strip().lower(), w_map["oscillation"])
    use_w = {k: weights[k] for k in factors if k in weights}
    ssum = sum(use_w.values()) or 1.0
    use_w = {k: v / ssum for k, v in use_w.items()}

    rows_out: List[Dict[str, Any]] = []
    for i, c in enumerate(codes):
        fr = {
            "reversal_5d": {"raw": ret5.get(c), "score": rev_rank[i] if i < len(rev_rank) else 50.0},
            "fund_flow_3d": {"raw": flow_scores.get(c), "score": flow_scores.get(c, 50.0)},
            "sector_momentum_5d": {
                "raw": sec_scores[i] if i < len(sec_scores) and np.isfinite(sec_scores[i]) else None,
                "score": sec_rank[i] if i < len(sec_rank) else 50.0,
            },
        }
        total = sum(use_w.get(fk, 0.0) * float(fr.get(fk, {}).get("score") or 50.0) for fk in factors)
        rows_out.append(
            {
                "symbol": c,
                "score": round(total, 4),
                "factors": {k: fr[k] for k in factors if k in fr},
                "industry": industry_of.get(c) or None,
            }
        )

    rows_out.sort(key=lambda x: x["score"], reverse=True)
    top_n = max(1, min(int(top_n or 10), len(rows_out)))
    picks = rows_out[:top_n]

    q_hist = ok_hist / max(len(codes), 1)
    quality_score = round(100.0 * (0.65 * q_hist + 0.35 * (1.0 if not degraded else 0.75)), 2)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "success": True,
        "message": "ok",
        "data": picks,
        "universe": universe,
        "universe_source": uni_src,
        "universe_size": len(codes),
        "factors_requested": factors,
        "neutralize_applied": neutralize,
        "regime_hint": regime_hint,
        "weights_effective": use_w,
        "quality_score": quality_score,
        "degraded": degraded,
        "degraded_notes": notes,
        "screening_date": screening_date,
        "config_hash": cfg_hash,
        "elapsed_ms": elapsed_ms,
        "plugin_version": _plugin_version(),
        "sw_mapping": {
            "mapping_version": sw_meta.get("mapping_version"),
            "coverage": round(cov, 4),
            "hit": hit,
            "total": tot,
        },
    }
