#!/usr/bin/env python3
"""
北向资金数据采集模块
数据源：东方财富沪深港通接口
"""

import requests
import json
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from contextlib import nullcontext

from plugins.data_collection.sentiment_common import (
    build_cache_key,
    cache_get,
    cache_set,
    infer_ttl_seconds,
    normalize_contract,
)

logger = logging.getLogger(__name__)

try:
    import tushare as ts  # type: ignore[import]
    TUSHARE_AVAILABLE = True
except Exception:
    ts = None  # type: ignore[assignment]
    TUSHARE_AVAILABLE = False

try:
    from plugins.utils.proxy_env import without_proxy_env
    PROXY_ENV_AVAILABLE = True
except Exception:
    PROXY_ENV_AVAILABLE = False

    def without_proxy_env(*args, **kwargs):  # type: ignore[no-redef]
        return nullcontext()


ENABLE_LEGACY_FALLBACK = str(os.environ.get("NORTHBOUND_ENABLE_LEGACY_FALLBACK", "true")).lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _get_tushare_pro():
    """Delegates to ``plugins.connectors.tushare.pro_client`` (P1-tushare migration anchor)."""
    from plugins.connectors.tushare.pro_client import get_tushare_pro as _g

    return _g()


def _has_tushare_token() -> bool:
    return bool((os.environ.get("TUSHARE_TOKEN") or "").strip())


def _is_trading_hours(dt: datetime) -> bool:
    if dt.weekday() >= 5:
        return False
    hm = dt.hour * 100 + dt.minute
    in_morning = 930 <= hm <= 1130
    in_afternoon = 1300 <= hm <= 1500
    return in_morning or in_afternoon


def _prev_trade_date(dt: datetime) -> str:
    d = dt - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _fmt_ymd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _mf_to_yi(v: Optional[str]) -> float:
    try:
        return float(v) / 100.0
    except Exception:
        return 0.0


def _build_tushare_payload(df: pd.DataFrame, query_trade_date: str, note: str) -> Dict:
    df = df.copy()
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date", ascending=False)
    rows: List[Dict] = []
    for _, r in df.iterrows():
        trade_date = str(r.get("trade_date") or "")
        ymd = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}" if len(trade_date) == 8 else trade_date
        hgt = _mf_to_yi(r.get("hgt"))
        sgt = _mf_to_yi(r.get("sgt"))
        north = _mf_to_yi(r.get("north_money"))
        south = _mf_to_yi(r.get("south_money"))
        rows.append(
            {
                "date": ymd,
                "sh_net": hgt,
                "sz_net": sgt,
                "total_net": north if north != 0 else hgt + sgt,
                "south_money": south,
            }
        )

    latest = rows[0] if rows else {"date": query_trade_date, "sh_net": 0.0, "sz_net": 0.0, "total_net": 0.0, "south_money": 0.0}
    totals = [x["total_net"] for x in rows]
    cum5 = round(sum(totals[:5]), 2) if totals else None
    cum20 = round(sum(totals[:20]), 2) if totals else None
    consecutive = 0
    if totals:
        sign = 1 if totals[0] > 0 else -1 if totals[0] < 0 else 0
        for v in totals:
            if sign == 0 or (v > 0 and sign > 0) or (v < 0 and sign < 0):
                consecutive += 1
            else:
                break

    signal = _generate_signal({"total_net": latest["total_net"]}, None, consecutive)
    return {
        "status": "success",
        "date": latest["date"],
        "data": {
            "sh_net": latest["sh_net"],
            "sz_net": latest["sz_net"],
            "total_net": latest["total_net"],
            "sh_buy": None,
            "sh_sell": None,
            "sz_buy": None,
            "sz_sell": None,
            "south_money": latest["south_money"],
        },
        "cumulative": {"5d": cum5, "20d": cum20},
        "statistics": {
            "avg_5d": round(sum(totals[:5]) / min(5, len(totals)), 2) if totals else None,
            "avg_20d": round(sum(totals[:20]) / min(20, len(totals)), 2) if totals else None,
            "consecutive_days": consecutive,
            "trend": "流入" if latest["total_net"] > 0 else "流出" if latest["total_net"] < 0 else "持平",
        },
        "signal": signal,
        "history": rows,
        "source": "tushare.moneyflow_hsgt",
        "note": note,
        "explanation": "Tushare 日频北向汇总数据（收盘后更新），盘中默认返回上一交易日。",
    }


def tool_fetch_northbound_flow(date: str = None, lookback_days: int = 1) -> Dict:
    """
    获取北向资金流向数据
    
    Args:
        date: 指定日期（YYYY-MM-DD），默认今天
        lookback_days: 回溯天数，用于获取历史数据
    
    Returns:
        包含北向资金流向数据的字典
    """
    cache_key = build_cache_key("northbound_tool", {"date": date, "lookback_days": lookback_days})
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
            quality_data_type="northbound",
        )

    attempts: List[Dict] = []
    try:
        # 默认今天
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now()
        query_trade_date = date.replace("-", "") if date else _fmt_ymd(now)
        note = ""
        if not date and _is_trading_hours(now):
            query_trade_date = _prev_trade_date(now)
            note = "盘中时段返回上一交易日收盘汇总。"

        pro = _get_tushare_pro()
        token_present = _has_tushare_token()
        if pro is not None:
            try:
                df_ts = pro.moneyflow_hsgt(trade_date=query_trade_date)
                ok = df_ts is not None and not df_ts.empty
                attempts.append({"source": "tushare.moneyflow_hsgt", "ok": ok, "message": f"trade_date={query_trade_date}"})
                if not ok:
                    # fallback to date range when trade_date empty (common in intraday / holiday)
                    start_date = (datetime.strptime(query_trade_date, "%Y%m%d") - timedelta(days=40)).strftime("%Y%m%d")
                    df_ts = pro.moneyflow_hsgt(start_date=start_date, end_date=query_trade_date)
                    ok = df_ts is not None and not df_ts.empty
                    attempts.append({"source": "tushare.moneyflow_hsgt", "ok": ok, "message": f"range={start_date}-{query_trade_date}"})
                if ok:
                    df_ts = df_ts.head(max(1, lookback_days))
                    payload = _build_tushare_payload(df_ts, query_trade_date, note)
                    cache_set(cache_key, payload, infer_ttl_seconds("northbound"))
                    return normalize_contract(
                        success=True,
                        payload=payload,
                        source=payload["source"],
                        attempts=attempts,
                        used_fallback=False,
                        data_quality="fresh" if not note else "previous_day_close",
                        cache_hit=False,
                        quality_data_type="northbound",
                    )
            except Exception as e:  # noqa: BLE001
                attempts.append({"source": "tushare.moneyflow_hsgt", "ok": False, "message": str(e)[:160]})
        else:
            reason = "tushare_not_installed" if not TUSHARE_AVAILABLE else "missing_tushare_token"
            attempts.append({"source": "tushare.moneyflow_hsgt", "ok": False, "message": reason})

        if not ENABLE_LEGACY_FALLBACK:
            err_code = "TOKEN_MISSING" if not token_present else "UPSTREAM_FETCH_FAILED"
            err_msg = (
                "TUSHARE_TOKEN 未配置，且已禁用 legacy 降级。"
                if not token_present
                else "Tushare 主源失败，且已禁用 legacy 降级。"
            )
            return normalize_contract(
                success=False,
                payload={
                    "status": "error",
                    "date": date if date else datetime.now().strftime("%Y-%m-%d"),
                    "explanation": err_msg,
                },
                source="northbound",
                attempts=attempts,
                used_fallback=False,
                data_quality="partial",
                cache_hit=False,
                error_code=err_code,
                error_message=err_msg,
                quality_data_type="northbound",
            )

        # 东方财富北向资金接口（AKShare summary 已移除，不再使用）
        url = "http://data.eastmoney.com/DataCenter_V3/Trade2014/HsgtFlow.ashx"
        
        params = {
            "mr": "0",
            "t": "slhfa",
            "cb": "",
            "js": "var t={pages:(pc),data:[(x)]}",
            "dpt": "zjtz",
            "style": "all",
            "sc": "rand",
            "st": "desc",
            "rt": ""
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://data.eastmoney.com/hsgt/"
        }
        
        from plugins.utils.throttled_http import run_bounded

        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            response = run_bounded(requests.get, url, params=params, headers=headers, timeout=10)
        response.encoding = "utf-8"
        
        # 解析JSONP响应
        text = (response.text or "").strip()
        if text.startswith("var t="):
            text = text.replace("var t=", "")
        # 兼容 UTF-8 BOM 与尾部分号
        text = text.lstrip("\ufeff").strip().rstrip(";").strip()
        
        data = json.loads(text)
        attempts.append({"source": "eastmoney.legacy_hsgt", "ok": True, "message": "ok"})
        
        if not data or "data" not in data:
            return {
                "status": "error",
                "error": "北向资金数据为空",
                "date": date
            }
        
        # 解析数据
        records = []
        for item in data["data"]:
            record = {
                "date": item[0],  # 日期
                "sh_buy": float(item[1]) if item[1] else 0,  # 沪股通买入（亿）
                "sh_sell": float(item[2]) if item[2] else 0,  # 沪股通卖出（亿）
                "sh_net": float(item[3]) if item[3] else 0,  # 沪股通净流入（亿）
                "sz_buy": float(item[4]) if item[4] else 0,  # 深股通买入（亿）
                "sz_sell": float(item[5]) if item[5] else 0,  # 深股通卖出（亿）
                "sz_net": float(item[6]) if item[6] else 0,  # 深股通净流入（亿）
                "total_net": float(item[7]) if item[7] else 0,  # 总净流入（亿）
            }
            records.append(record)
        
        # 转换为DataFrame
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date", ascending=False)
        
        # 截取指定天数
        df = df.head(lookback_days)
        
        # 计算统计信息
        latest = df.iloc[0].to_dict()
        latest["date"] = latest["date"].strftime("%Y-%m-%d")
        
        # 历史对比
        if len(df) >= 5:
            avg_5d = df.head(5)["total_net"].mean()
            avg_20d = df.head(20)["total_net"].mean() if len(df) >= 20 else None
        else:
            avg_5d = None
            avg_20d = None
        
        # 连续流入/流出
        consecutive_days = 0
        for _, row in df.iterrows():
            if (row["total_net"] > 0 and latest["total_net"] > 0) or \
               (row["total_net"] < 0 and latest["total_net"] < 0):
                consecutive_days += 1
            else:
                break
        
        # 生成信号
        signal = _generate_signal(latest, avg_5d, consecutive_days)
        
        payload = {
            "status": "success",
            "date": latest["date"],
            "data": {
                "sh_net": latest["sh_net"],
                "sz_net": latest["sz_net"],
                "total_net": latest["total_net"],
                "sh_buy": latest["sh_buy"],
                "sh_sell": latest["sh_sell"],
                "sz_buy": latest["sz_buy"],
                "sz_sell": latest["sz_sell"]
            },
            "statistics": {
                "avg_5d": round(avg_5d, 2) if avg_5d else None,
                "avg_20d": round(avg_20d, 2) if avg_20d else None,
                "consecutive_days": consecutive_days,
                "trend": "流入" if latest["total_net"] > 0 else "流出"
            },
            "signal": signal,
            "history": df.head(lookback_days).to_dict("records"),
            "source": "eastmoney.legacy_hsgt",
            "note": "Tushare 不可用时回退到 legacy 接口；该链路字段稳定性较弱。",
            "explanation": "主源 tushare.moneyflow_hsgt 失败后降级到 legacy 以保证可用性。",
        }
        cache_set(cache_key, payload, infer_ttl_seconds("northbound"))
        return normalize_contract(
            success=True,
            payload=payload,
            source=payload["source"],
            attempts=attempts,
            used_fallback=True,
            data_quality="partial",
            cache_hit=False,
            quality_data_type="northbound",
        )
        
    except Exception as e:
        logger.error(f"获取北向资金数据失败: {e}")
        attempts.append({"source": "eastmoney.legacy_hsgt", "ok": False, "message": str(e)[:160]})
        return normalize_contract(
            success=False,
            payload={
                "status": "error",
                "date": date if date else datetime.now().strftime("%Y-%m-%d"),
                "explanation": "北向主源与降级源均失败，请稍后重试。",
            },
            source="northbound",
            attempts=attempts,
            used_fallback=False,
            data_quality="partial",
            cache_hit=False,
            error_code="UPSTREAM_FETCH_FAILED",
            error_message=str(e),
            quality_data_type="northbound",
        )


def _generate_signal(latest: Dict, avg_5d: Optional[float], consecutive_days: int) -> Dict:
    """
    生成北向资金信号
    
    Args:
        latest: 最新数据
        avg_5d: 5日均值
        consecutive_days: 连续流入/流出天数
    
    Returns:
        信号字典
    """
    total_net = latest["total_net"]
    
    # 信号强度判断
    if total_net > 100:
        strength = "strong_buy"
        confidence = 0.85
        description = "大幅流入（>100亿），强烈看多"
    elif total_net > 50:
        strength = "buy"
        confidence = 0.75
        description = "显著流入（>50亿），看多"
    elif total_net > 20:
        strength = "light_buy"
        confidence = 0.65
        description = "小幅流入（>20亿），偏多"
    elif total_net > 0:
        strength = "neutral_positive"
        confidence = 0.55
        description = "微幅流入，中性偏多"
    elif total_net > -20:
        strength = "neutral_negative"
        confidence = 0.55
        description = "微幅流出，中性偏空"
    elif total_net > -50:
        strength = "sell"
        confidence = 0.65
        description = "显著流出（>50亿），风险"
    else:
        strength = "strong_sell"
        confidence = 0.75
        description = "大幅流出（>50亿），强烈风险信号"
    
    # 趋势确认
    if consecutive_days >= 3:
        if total_net > 0:
            description += f"，连续{consecutive_days}日流入，趋势确认"
            confidence = min(confidence + 0.1, 0.95)
        else:
            description += f"，连续{consecutive_days}日流出，风险确认"
            confidence = min(confidence + 0.1, 0.95)
    
    # 对比5日均值
    if avg_5d and abs(total_net) > abs(avg_5d) * 1.5:
        description += f"，超预期（5日均值{avg_5d:.2f}亿）"
        confidence = min(confidence + 0.05, 0.95)
    
    return {
        "strength": strength,
        "confidence": round(confidence, 2),
        "description": description,
        "action": "关注" if total_net > 20 else "观望" if total_net > -20 else "风险"
    }


if __name__ == "__main__":
    # 测试
    result = tool_fetch_northbound_flow(lookback_days=5)
    print(json.dumps(result, indent=2, ensure_ascii=False))
