"""
涨停股数据管道：获取指定日期的涨停股列表，支持多日区间。
数据源：
- 主池: stock_zt_pool_em
- 专项: stock_zt_pool_previous_em
- 补充: stock_zt_pool_strong_em / stock_zt_pool_sub_new_em
链路: em -> previous -> strong -> sub_new -> cache
"""

from __future__ import annotations

import logging
import time
from contextlib import nullcontext
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

from plugins.data_collection.sentiment_common import (
    build_cache_key,
    cache_get,
    cache_set,
    infer_ttl_seconds,
    normalize_contract,
    quality_gate_records,
)

logger = logging.getLogger(__name__)

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

try:
    from plugins.utils.proxy_env import without_proxy_env

    PROXY_ENV_AVAILABLE = True
except Exception:
    PROXY_ENV_AVAILABLE = False

    def without_proxy_env(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        return nullcontext()

# 列名映射（akshare 返回中文列名）
COL_CODE = "代码"
COL_NAME = "名称"
COL_CHANGE_PCT = "涨跌幅"
COL_PRICE = "最新价"
COL_TURNOVER_RATE = "换手率"
COL_FLOAT_MV = "流通市值"
COL_FIRST_SEAL_TIME = "首次封板时间"
COL_LAST_SEAL_TIME = "最后封板时间"
COL_BOARD = "所属行业"
COL_CONTINUOUS = "连板数"
COL_AMOUNT = "成交额"
COL_BROKEN = "炸板次数"


def _parse_seal_time(s: Any) -> Optional[str]:
    """解析首次封板时间 例如 092500 -> 09:25:00"""
    if s is None or (isinstance(s, float) and (s != s)):
        return None
    s = str(s).strip()
    if len(s) == 6 and s.isdigit():
        return f"{s[:2]}:{s[2:4]}:{s[4:6]}"
    return s


def _is_tail_limit_up(first_seal_time: Optional[str], last_seal_time: Optional[str]) -> bool:
    """尾盘涨停：14:30 之后首次封板或最后封板视为尾盘"""
    for t in (first_seal_time, last_seal_time):
        if not t or ":" not in str(t):
            continue
        parts = str(t).strip().split(":")
        if len(parts) >= 2:
            try:
                h, m = int(parts[0]), int(parts[1])
                if h > 14 or (h == 14 and m >= 30):
                    return True
            except ValueError:
                pass
    return False


def _filter_row(row: Dict[str, Any], exclude_st: bool = True, exclude_sub_new: bool = True) -> bool:
    """True 表示保留，False 表示过滤掉"""
    name = str(row.get("name", "") or "")
    code = str(row.get("code", "") or "")
    turnover_rate = row.get("turnover_rate")
    if exclude_st and ("ST" in name or "st" in name or code.startswith("3") and "ST" in name.upper()):
        return False
    if turnover_rate is not None:
        try:
            tr = float(turnover_rate)
            if tr > 30.0:  # 换手率>30% 可能是出货
                return False
        except (TypeError, ValueError):
            pass
    # 次新股需上市日期，此处暂不实现（可后续接 wind/tushare 上市日）
    if exclude_sub_new:
        pass  # 保留，后续有数据再过滤
    return True


def _fetch_limit_up_akshare(date: str) -> Optional[List[Dict[str, Any]]]:
    """AKShare 获取单日涨停池。date 格式 YYYYMMDD"""
    if not AKSHARE_AVAILABLE:
        return None
    try:
        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            df = ak.stock_zt_pool_em(date)
        if df is None or df.empty:
            return []
        rows = []
        for _, r in df.iterrows():
            first_seal = _parse_seal_time(r.get(COL_FIRST_SEAL_TIME))
            last_seal = _parse_seal_time(r.get(COL_LAST_SEAL_TIME))
            if _is_tail_limit_up(first_seal, last_seal):
                continue
            try:
                float_mv = r.get(COL_FLOAT_MV)
                if hasattr(float_mv, "item"):
                    float_mv = float(float_mv)
                else:
                    float_mv = float(float_mv) if float_mv is not None else None
            except (TypeError, ValueError):
                float_mv = None
            try:
                turnover_rate = r.get(COL_TURNOVER_RATE)
                if turnover_rate is not None:
                    turnover_rate = float(turnover_rate)
            except (TypeError, ValueError):
                turnover_rate = None
            continuous = r.get(COL_CONTINUOUS)
            if continuous is not None:
                try:
                    continuous = int(float(continuous))
                except (TypeError, ValueError):
                    continuous = None
            item = {
                "code": str(r.get(COL_CODE, "")).strip(),
                "name": str(r.get(COL_NAME, "")).strip(),
                "limit_up_time": first_seal or last_seal,
                "change_pct": float(r.get(COL_CHANGE_PCT, 0)) if r.get(COL_CHANGE_PCT) is not None else None,
                "turnover_rate": turnover_rate,
                "float_mv": float_mv,
                "board_name": str(r.get(COL_BOARD, "")).strip() or None,
                "continuous_limit_up_count": continuous,
                "latest_price": float(r.get(COL_PRICE)) if r.get(COL_PRICE) is not None else None,
                "amount": float(r.get(COL_AMOUNT)) if r.get(COL_AMOUNT) is not None else None,
            }
            if not _filter_row(item):
                continue
            rows.append(item)
        return rows
    except Exception as e:
        logger.warning("akshare stock_zt_pool_em failed for %s: %s", date, e)
        return None


def _fetch_pool_df(func_name: str, date: str) -> Tuple[Optional[Any], Optional[str]]:
    if not AKSHARE_AVAILABLE:
        return None, "akshare_not_available"
    try:
        fn = getattr(ak, func_name)
    except AttributeError:
        return None, "function_not_found"
    try:
        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            df = fn(date=date)
        return df, None
    except Exception as e:
        return None, str(e)[:220]


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _extract_main_rows_from_df(df: Any) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        first_seal = _parse_seal_time(r.get(COL_FIRST_SEAL_TIME))
        last_seal = _parse_seal_time(r.get(COL_LAST_SEAL_TIME))
        if _is_tail_limit_up(first_seal, last_seal):
            continue
        item = {
            "code": str(r.get(COL_CODE, "")).strip(),
            "name": str(r.get(COL_NAME, "")).strip(),
            "limit_up_time": first_seal or last_seal,
            "change_pct": _to_float(r.get(COL_CHANGE_PCT)),
            "turnover_rate": _to_float(r.get(COL_TURNOVER_RATE)),
            "float_mv": _to_float(r.get(COL_FLOAT_MV)),
            "board_name": str(r.get(COL_BOARD, "")).strip() or None,
            "continuous_limit_up_count": int(float(r.get(COL_CONTINUOUS))) if r.get(COL_CONTINUOUS) is not None else None,
            "latest_price": _to_float(r.get(COL_PRICE)),
            "amount": _to_float(r.get(COL_AMOUNT)),
            "broken_count_item": int(float(r.get(COL_BROKEN) or 0)),
        }
        if _filter_row(item):
            rows.append(item)
    return rows


def _prev_calendar_date(date: str) -> str:
    try:
        dt = datetime.strptime(date, "%Y%m%d")
    except ValueError:
        return date
    prev = dt - timedelta(days=1)
    return prev.strftime("%Y%m%d")


def _is_same_day_intraday(date: str) -> bool:
    """
    盘中窗口判断：当天且 15:10 前。
    目的：避免盘中涨停池尚未完全展开时触发过严质量闸门。
    """
    try:
        now = datetime.now().astimezone()
        if date != now.strftime("%Y%m%d"):
            return False
        hm = now.hour * 60 + now.minute
        return hm < (15 * 60 + 10)
    except Exception:
        return False


def _calc_sentiment_stage(metrics: Dict[str, float]) -> Dict[str, Any]:
    # 100-point weighted model:
    # 主生态 40, 昨日延续 35, 强势扩散 15, 次新活跃 10
    score = 0.0
    confidence_weight = 0.0

    limit_up_count = float(metrics.get("limit_up_count", 0))
    max_height = float(metrics.get("max_continuous_height", 0))
    broken_rate = metrics.get("broken_rate")
    if limit_up_count > 80:
        score += 20
    elif limit_up_count > 50:
        score += 14
    elif limit_up_count > 30:
        score += 8
    confidence_weight += 20
    if max_height >= 5:
        score += 12
    elif max_height >= 3:
        score += 8
    confidence_weight += 12
    if broken_rate is not None:
        br = float(broken_rate)
        score += max(0.0, 8 * (1.0 - min(br, 1.0)))
        confidence_weight += 8

    prev_mean = metrics.get("prev_mean")
    prev_median = metrics.get("prev_median")
    prev_positive_ratio = metrics.get("prev_positive_ratio")
    if prev_mean is not None:
        score += max(0.0, min(15.0, 7.5 + float(prev_mean)))
        confidence_weight += 15
    if prev_median is not None:
        score += max(0.0, min(10.0, 5.0 + float(prev_median)))
        confidence_weight += 10
    if prev_positive_ratio is not None:
        score += max(0.0, min(10.0, 10.0 * float(prev_positive_ratio)))
        confidence_weight += 10

    strong_pool_count = metrics.get("strong_pool_count")
    if strong_pool_count is not None:
        score += min(10.0, float(strong_pool_count) / 30.0)
        confidence_weight += 10
    top_sector_concentration = metrics.get("top_sector_concentration")
    if top_sector_concentration is not None:
        score += min(5.0, 5.0 * float(top_sector_concentration))
        confidence_weight += 5

    sub_new_pool_count = metrics.get("sub_new_pool_count")
    if sub_new_pool_count is not None:
        score += min(10.0, float(sub_new_pool_count) / 15.0)
        confidence_weight += 10

    # Missing segment re-normalization
    final_score = (score / confidence_weight * 100.0) if confidence_weight > 0 else 0.0
    score = max(0.0, min(100.0, final_score))
    if score >= 60:
        stage = "高潮期"
    elif score >= 30:
        stage = "修复期"
    elif score >= 10:
        stage = "冰点期"
    else:
        stage = "退潮期"
    return {"score": round(score, 2), "stage": stage, "confidence_weight": round(confidence_weight, 2)}


def tool_fetch_limit_up_stocks(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exclude_st: bool = True,
    exclude_tail_limit_up: bool = True,
) -> Dict[str, Any]:
    """
    获取涨停股列表。
    参数:
      date: 单日 YYYYMMDD
      start_date, end_date: 区间 YYYYMMDD，与 date 二选一
      exclude_st: 是否排除 ST
      exclude_tail_limit_up: 是否排除尾盘涨停(14:30后)
    返回:
      success, data: [{ code, name, limit_up_time, change_pct, turnover_rate, float_mv, board_name, continuous_limit_up_count, ... }], date(s), count
    """
    cache_key = build_cache_key(
        "limit_up_tool",
        {
            "date": date,
            "start_date": start_date,
            "end_date": end_date,
            "exclude_st": exclude_st,
            "exclude_tail_limit_up": exclude_tail_limit_up,
        },
    )
    cached = cache_get(cache_key)
    if cached is not None:
        return normalize_contract(
            success=True,
            payload=cached,
            source=cached.get("source", "cache"),
            attempts=[{"source": "cache", "ok": True, "message": "hit"}],
            fallback_route=["cache"],
            used_fallback=True,
            data_quality="cached",
            cache_hit=True,
            quality_data_type="limit_up",
        )

    if date:
        dates = [date]
    elif start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")
            dates = []
            d = start
            while d <= end:
                dates.append(d.strftime("%Y%m%d"))
                d += timedelta(days=1)
        except ValueError as e:
            return {"success": False, "error": f"日期格式错误: {e}", "data": [], "count": 0}
    else:
        # 默认今日
        dates = [datetime.now().strftime("%Y%m%d")]

    all_rows: List[Dict[str, Any]] = []
    all_codes: set[str] = set()
    attempts: List[Dict[str, Any]] = []
    previous_changes: List[float] = []
    strong_pool_count = 0
    sub_new_pool_count = 0
    source_used = "cache"
    broken_count = 0

    spacing_cfg: Dict[str, Any] | None = None
    try:
        from src.config_loader import load_system_config

        spacing_cfg = load_system_config(use_cache=True)
    except Exception:
        spacing_cfg = None
    try:
        from plugins.utils.upstream_spacing import sleep_limit_up_between_pools
    except Exception:

        def sleep_limit_up_between_pools(_cfg: Dict[str, Any] | None, *, after_step: int) -> None:  # type: ignore[no-redef]
            if after_step >= 1:
                time.sleep(0.35)

    chain_step = 0
    for d in dates:
        intraday_mode = _is_same_day_intraday(d)
        # approved chain: em -> previous -> strong -> sub_new -> cache
        em_df, em_err = _fetch_pool_df("stock_zt_pool_em", d)
        if em_df is not None and not em_df.empty:
            source_used = "akshare.stock_zt_pool_em"
            attempts.append({"source": "akshare.stock_zt_pool_em", "ok": True, "message": d})
            rows = _extract_main_rows_from_df(em_df)
            for r in rows:
                r["date"] = d
                code = str(r.get("code") or "")
                if code and code not in all_codes:
                    all_rows.append(r)
                    all_codes.add(code)
            if COL_BROKEN in em_df.columns:
                try:
                    broken_count += int(em_df[COL_BROKEN].fillna(0).astype(float).sum())
                except Exception:
                    pass
        else:
            attempts.append(
                {"source": "akshare.stock_zt_pool_em", "ok": False, "message": em_err or f"empty:{d}"}
            )

        chain_step += 1
        sleep_limit_up_between_pools(spacing_cfg, after_step=chain_step)
        prev_df, prev_err = _fetch_pool_df("stock_zt_pool_previous_em", d)
        if prev_df is not None and not prev_df.empty:
            attempts.append({"source": "akshare.stock_zt_pool_previous_em", "ok": True, "message": d})
            if COL_CHANGE_PCT in prev_df.columns:
                for v in prev_df[COL_CHANGE_PCT].tolist():
                    fv = _to_float(v)
                    if fv is not None:
                        previous_changes.append(fv)
        else:
            attempts.append(
                {"source": "akshare.stock_zt_pool_previous_em", "ok": False, "message": prev_err or f"empty:{d}"}
            )

        chain_step += 1
        sleep_limit_up_between_pools(spacing_cfg, after_step=chain_step)
        strong_df, strong_err = _fetch_pool_df("stock_zt_pool_strong_em", d)
        if strong_df is not None and not strong_df.empty:
            attempts.append({"source": "akshare.stock_zt_pool_strong_em", "ok": True, "message": d})
            strong_pool_count += int(len(strong_df))
            # 盘中阶段主池样本过少时，用 strong 池补齐可交易热度样本（保持去重）。
            if intraday_mode and len(all_rows) < 5:
                strong_rows = _extract_main_rows_from_df(strong_df)
                for r in strong_rows:
                    r["date"] = d
                    code = str(r.get("code") or "")
                    if code and code not in all_codes:
                        all_rows.append(r)
                        all_codes.add(code)
                if strong_rows:
                    source_used = "akshare.stock_zt_pool_strong_em+em"
        else:
            attempts.append(
                {"source": "akshare.stock_zt_pool_strong_em", "ok": False, "message": strong_err or f"empty:{d}"}
            )

        chain_step += 1
        sleep_limit_up_between_pools(spacing_cfg, after_step=chain_step)
        sub_df, sub_err = _fetch_pool_df("stock_zt_pool_sub_new_em", d)
        if sub_df is not None and not sub_df.empty:
            attempts.append({"source": "akshare.stock_zt_pool_sub_new_em", "ok": True, "message": d})
            sub_new_pool_count += int(len(sub_df))
        else:
            attempts.append(
                {"source": "akshare.stock_zt_pool_sub_new_em", "ok": False, "message": sub_err or f"empty:{d}"}
            )

    min_records = 1 if len(dates) > 1 else (3 if any(_is_same_day_intraday(d) for d in dates) else 5)
    gate = quality_gate_records(
        all_rows,
        min_records=min_records,
        required_fields=["code", "name", "change_pct", "continuous_limit_up_count"],
    )
    if not gate["ok"] and cached is None:
        return normalize_contract(
            success=False,
            payload={
                "data": [],
                "dates": dates,
                "count": 0,
                "quality_gate": gate,
                "explanation": "涨停池质量闸门未通过，当前无可用缓存可回退。",
            },
            source="akshare.stock_zt_pool_em",
            attempts=attempts,
            used_fallback=False,
            data_quality="partial",
            cache_hit=False,
            error_code="UPSTREAM_FETCH_FAILED",
            error_message=gate["reason"],
            quality_data_type="limit_up",
        )

    prev_perf_mean = round(sum(previous_changes) / len(previous_changes), 4) if previous_changes else None
    prev_perf_median = round(float(median(previous_changes)), 4) if previous_changes else None
    prev_positive_ratio = (
        round(sum(1 for x in previous_changes if x > 0) / len(previous_changes), 4) if previous_changes else None
    )

    max_height = 0
    board_map: Dict[str, int] = {}
    for row in all_rows:
        try:
            max_height = max(max_height, int(row.get("continuous_limit_up_count") or 0))
        except Exception:
            pass
        board = (row.get("board_name") or "未分类").strip() if isinstance(row.get("board_name"), str) else "未分类"
        board_map[board] = board_map.get(board, 0) + 1
    top_boards = sorted(board_map.items(), key=lambda x: x[1], reverse=True)[:10]
    top_sector_concentration = (
        round((top_boards[0][1] / len(all_rows)), 4) if top_boards and len(all_rows) > 0 else None
    )
    broken_rate = (
        round(broken_count / float(len(all_rows) + broken_count), 4) if (len(all_rows) + broken_count) > 0 else None
    )

    sentiment = _calc_sentiment_stage(
        {
            "limit_up_count": len(all_rows),
            "broken_rate": broken_rate,
            "max_continuous_height": max_height,
            "prev_mean": prev_perf_mean,
            "prev_median": prev_perf_median,
            "prev_positive_ratio": prev_positive_ratio,
            "strong_pool_count": strong_pool_count,
            "top_sector_concentration": top_sector_concentration,
            "sub_new_pool_count": sub_new_pool_count,
        }
    )
    payload = {
        "data": all_rows,
        "dates": dates,
        "count": len(all_rows),
        "limit_up_count": len(all_rows),
        "max_continuous_height": max_height,
        "broken_count": broken_count,
        "broken_rate": broken_rate,
        "prev_limit_up_perf_mean": prev_perf_mean,
        "prev_limit_up_perf_median": prev_perf_median,
        "prev_limit_up_positive_ratio": prev_positive_ratio,
        "strong_pool_count": strong_pool_count,
        "sub_new_pool_count": sub_new_pool_count,
        "limit_up_by_sector": [{"sector": k, "count": v} for k, v in top_boards],
        "top_sector_concentration": top_sector_concentration,
        "sentiment_stage": sentiment,
        "metric_weights": {
            "main_ecology": 40,
            "prev_limit_up_extension": 35,
            "strong_expansion": 15,
            "sub_new_activity": 10,
        },
        "quality_gate": gate,
        "explanation": "主口径(em) + 专项(previous) + 补充(strong/sub_new)计算情绪阶段，缺失项自动重标化。",
    }
    ttl = infer_ttl_seconds("limit_up")
    cache_set(cache_key, payload, ttl)
    return normalize_contract(
        success=True,
        payload=payload,
        source=source_used,
        attempts=attempts,
        used_fallback=source_used != "akshare.stock_zt_pool_em",
        data_quality="fresh",
        cache_hit=False,
        quality_data_type="limit_up",
        quality_min_records=5 if len(dates) == 1 else 1,
    )
