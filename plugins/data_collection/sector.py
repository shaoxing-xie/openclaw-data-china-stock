#!/usr/bin/env python3
"""
板块轮动数据采集模块

全列表截面优先级（尽量弱化东财 JSONP / 单 host push2）：
- 行业：同花顺 industry_summary_ths → 新浪 stock_sector_spot(新浪行业/行业) → 东财 push2 → AkShare stock_board_industry_name_em
- 概念：新浪 stock_sector_spot(概念) → AkShare stock_board_concept_name_em(push2) → 东财 GetConcept JSONP

period（today/week/month）仅对东财概念 JSONP 路径有效；THS/新浪为当前截面快照。
"""

import requests
import json
import pandas as pd
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging
from contextlib import nullcontext

from plugins.data_collection.sentiment_common import (
    build_cache_key,
    cache_get,
    cache_set,
    infer_ttl_seconds,
    normalize_contract,
    quality_gate_records,
)

logger = logging.getLogger(__name__)

_TOP5_HISTORY: Dict[str, List[List[str]]] = {"industry": [], "concept": []}

try:
    from plugins.utils.proxy_env import without_proxy_env
    PROXY_ENV_AVAILABLE = True
except Exception:
    PROXY_ENV_AVAILABLE = False

    def without_proxy_env(*args, **kwargs):  # type: ignore[no-redef]
        return nullcontext()


def tool_fetch_sector_data(sector_type: str = "industry", period: str = "today") -> Dict:
    """
    获取板块轮动数据
    
    Args:
        sector_type: "industry"（行业板块）或 "concept"（概念板块）
        period: "today"（今日）/ "week"（本周）/ "month"（本月）
    
    Returns:
        包含板块涨跌幅数据的字典
    """
    sector_type = (sector_type or "industry").strip().lower()
    cache_key = build_cache_key("sector_tool", {"sector_type": sector_type, "period": period})
    cached = cache_get(cache_key)
    if cached is not None:
        return normalize_contract(
            success=True,
            payload=cached,
            source=cached.get("data_source", "cache"),
            attempts=[{"source": "cache", "ok": True, "message": "hit"}],
            used_fallback=True,
            data_quality="cached",
            cache_hit=True,
        )
    if sector_type not in ("industry", "concept"):
        return {
            "status": "error",
            "error": 'sector_type 须为 "industry" 或 "concept"',
            "sector_type": sector_type,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

    attempts: List[Dict[str, Any]] = []

    # ----- 行业：同花顺一览 → 新浪 → 东财 push2 → AkShare -----
    if sector_type == "industry":
        chain: List[Tuple[str, Callable[[], Optional[pd.DataFrame]]]] = [
            ("ths_industry_summary", _fetch_sector_from_ths_industry_summary),
            ("sina_新浪行业", lambda: _fetch_sector_from_sina("新浪行业")),
            ("sina_行业", lambda: _fetch_sector_from_sina("行业")),
            ("em_push2_industry", lambda: _fetch_sector_data_from_eastmoney(sector_type="industry", period=period)),
            ("akshare_industry_name_em", lambda: _fetch_sector_data_from_akshare(sector_type="industry")),
        ]
        for src, fetcher in chain:
            try:
                df = fetcher()
                if df is None or df.empty:
                    attempts.append({"source": src, "ok": False, "message": "empty dataframe"})
                    continue
                gate = quality_gate_records(
                    df.to_dict("records"),
                    min_records=30,
                    required_fields=["sector_name", "change_percent"],
                )
                if not gate.get("ok"):
                    attempts.append(
                        {
                            "source": src,
                            "ok": False,
                            "message": f"quality gate failed: {gate.get('reason', 'unknown')}",
                        }
                    )
                    continue
                attempts.append({"source": src, "ok": True, "message": "ok"})
                return _finalize_sector_response(df, sector_type, src, cache_key, attempts=attempts)
            except Exception as e:  # noqa: BLE001
                logger.warning("行业板块数据源 %s 失败: %s", src, e)
                attempts.append({"source": src, "ok": False, "message": str(e)[:160]})
        return normalize_contract(
            success=False,
            payload={
                "status": "error",
                "error": "行业板块：同花顺/新浪/东财/AkShare 均无有效数据",
                "sector_type": sector_type,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "explanation": "所有上游链路均失败且缓存未命中，按规则不使用估计值。",
            },
            source="sector",
            attempts=attempts,
            used_fallback=False,
            data_quality="partial",
            cache_hit=False,
            error_code="UPSTREAM_FETCH_FAILED",
            error_message="all sector upstream sources failed",
        )

    # ----- 概念：新浪截面 → 东财概念 clist → 东财 JSONP -----
    chain = [
        ("sina_概念", lambda: _fetch_sector_from_sina("概念")),
        ("em_concept_clist", _fetch_sector_from_em_concept_clist),
        ("em_concept_jsonp", lambda: _fetch_sector_data_from_eastmoney(sector_type="concept", period=period)),
    ]
    for src, fetcher in chain:
        try:
            df = fetcher()
            if df is None or df.empty:
                attempts.append({"source": src, "ok": False, "message": "empty dataframe"})
                continue
            gate = quality_gate_records(
                df.to_dict("records"),
                min_records=10,
                required_fields=["sector_name", "change_percent"],
            )
            if not gate.get("ok"):
                attempts.append(
                    {
                        "source": src,
                        "ok": False,
                        "message": f"quality gate failed: {gate.get('reason', 'unknown')}",
                    }
                )
                continue
            attempts.append({"source": src, "ok": True, "message": "ok"})
            return _finalize_sector_response(df, sector_type, src, cache_key, attempts=attempts)
        except Exception as e:  # noqa: BLE001
            logger.warning("概念板块数据源 %s 失败: %s", src, e)
            attempts.append({"source": src, "ok": False, "message": str(e)[:160]})
    return normalize_contract(
        success=False,
        payload={
            "status": "error",
            "error": "概念板块：新浪/东财均无有效数据",
            "sector_type": sector_type,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "explanation": "所有上游链路均失败且缓存未命中，按规则不使用估计值。",
        },
        source="sector",
        attempts=attempts,
        used_fallback=False,
        data_quality="partial",
        cache_hit=False,
        error_code="UPSTREAM_FETCH_FAILED",
        error_message="all concept upstream sources failed",
    )


def _fetch_sector_from_ths_industry_summary() -> Optional[pd.DataFrame]:
    """同花顺行业一览（AkShare stock_board_industry_summary_ths），全表截面。"""
    try:
        import akshare as ak  # type: ignore[import]
    except Exception as e:  # noqa: BLE001
        logger.error("AkShare 未安装: %s", e)
        return None
    try:
        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            raw = ak.stock_board_industry_summary_ths()
    except Exception as e:  # noqa: BLE001
        logger.warning("stock_board_industry_summary_ths 失败: %s", e)
        return None
    if raw is None or raw.empty or "板块" not in raw.columns or "涨跌幅" not in raw.columns:
        return None
    if "净流入" in raw.columns:
        net_inflow = pd.to_numeric(raw["净流入"], errors="coerce").fillna(0.0)
    else:
        net_inflow = 0.0
    df = pd.DataFrame(
        {
            "sector_name": raw["板块"].astype(str).str.strip(),
            "change_percent": pd.to_numeric(raw["涨跌幅"], errors="coerce"),
            "net_inflow": net_inflow,
        }
    )
    df["net_inflow"] = pd.to_numeric(df["net_inflow"], errors="coerce").fillna(0.0)
    df = df[(df["sector_name"].str.len() > 0) & (df["change_percent"].notna())]
    return df if not df.empty else None


def _fetch_sector_from_sina(indicator: str) -> Optional[pd.DataFrame]:
    """新浪板块截面（AkShare stock_sector_spot），indicator 见 AkShare 文档。"""
    try:
        import akshare as ak  # type: ignore[import]
    except Exception as e:  # noqa: BLE001
        logger.error("AkShare 未安装: %s", e)
        return None
    try:
        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            raw = ak.stock_sector_spot(indicator=indicator)
    except Exception as e:  # noqa: BLE001
        logger.warning("stock_sector_spot(%s) 失败: %s", indicator, e)
        return None
    if raw is None or raw.empty or "板块" not in raw.columns or "涨跌幅" not in raw.columns:
        return None
    df = pd.DataFrame(
        {
            "sector_name": raw["板块"].astype(str).str.strip(),
            "change_percent": pd.to_numeric(raw["涨跌幅"], errors="coerce"),
            "net_inflow": 0.0,
        }
    )
    df = df[(df["sector_name"].str.len() > 0) & (df["change_percent"].notna())]
    return df if not df.empty else None


def _fetch_sector_from_em_concept_clist() -> Optional[pd.DataFrame]:
    """东财概念板块全表（AkShare stock_board_concept_name_em，push2 分页）。"""
    try:
        import akshare as ak  # type: ignore[import]
    except Exception as e:  # noqa: BLE001
        logger.error("AkShare 未安装: %s", e)
        return None
    try:
        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            raw = ak.stock_board_concept_name_em()
    except Exception as e:  # noqa: BLE001
        logger.warning("stock_board_concept_name_em 失败: %s", e)
        return None
    if raw is None or raw.empty:
        return None
    name_col = "板块名称" if "板块名称" in raw.columns else None
    chg_col = "涨跌幅" if "涨跌幅" in raw.columns else None
    if not name_col or not chg_col:
        for c in raw.columns:
            s = str(c)
            if name_col is None and "名称" in s:
                name_col = c
            if chg_col is None and "涨跌幅" in s:
                chg_col = c
    if not name_col or not chg_col:
        return None
    net_col = None
    for c in raw.columns:
        if "净流入" in str(c):
            net_col = c
            break
    df = pd.DataFrame(
        {
            "sector_name": raw[name_col].astype(str).str.strip(),
            "change_percent": pd.to_numeric(raw[chg_col], errors="coerce"),
            "net_inflow": pd.to_numeric(raw[net_col], errors="coerce").fillna(0.0) if net_col else 0.0,
        }
    )
    df = df[(df["sector_name"].str.len() > 0) & (df["change_percent"].notna())]
    return df if not df.empty else None


def _fetch_sector_data_from_eastmoney(sector_type: str, period: str) -> Optional[pd.DataFrame]:
    """从东方财富 JSONP 接口获取板块数据，返回 DataFrame 或 None。"""
    # 根据类型选择不同的接口
    if sector_type == "industry":
        # 行业板块：DataCenter_V3 经常返回跳转 HTML；改为直连 push2 行业板块列表（与 AkShare stock_board_industry_name_em 同源）
        return _fetch_sector_data_from_eastmoney_push2_industry()
    else:  # concept
        # 概念板块接口
        url = "http://data.eastmoney.com/DataCenter_V3/Concept/GetConcept.ashx"
        params = {
            "code": "all",
            "type": period or "today",
            "sty": "f14",
            "js": "var data={pages:(pc),data:[(x)]}",
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://data.eastmoney.com/bkzj/",
    }

    ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
    with ctx:
        response = requests.get(url, params=params, headers=headers, timeout=10)
    response.encoding = "utf-8"

    text = response.text.strip()
    if not text:
        raise ValueError("东方财富返回空响应")
    if text.startswith("var data="):
        text = text.replace("var data=", "", 1)
    # 兼容 UTF-8 BOM
    text = text.lstrip("\ufeff")
    # 常见尾部分号/多余空白
    text = text.strip().rstrip(";").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 兜底：从文本中抽取 JSON 对象片段
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise
    if not data or "data" not in data:
        raise ValueError("东方财富板块数据为空")

    records = []
    items = data.get("data") or []
    for item in items:
        # 兼容两种格式：list 与 dict
        if isinstance(item, dict):
            name_val = str(item.get("sector_name") or item.get("name") or item.get("f14") or "").strip()
            if not name_val:
                continue
            try:
                change = float(item.get("change_percent") or item.get("pct") or item.get("f3") or 0)
            except Exception:
                change = 0.0
            records.append({"sector_name": name_val, "change_percent": change, "net_inflow": 0.0})
            continue

        if not isinstance(item, (list, tuple)) or len(item) < 4:
            continue
        try:
            records.append(
                {
                    "sector_name": item[1] if len(item) > 1 else "",
                    "current_price": float(item[2]) if len(item) > 2 else 0,
                    "change_percent": float(item[3]) if len(item) > 3 else 0,
                    "volume": float(item[5]) if len(item) > 5 else 0,
                    "turnover": float(item[6]) if len(item) > 6 else 0,
                    "inflow": float(item[7]) if len(item) > 7 else 0,
                    "outflow": float(item[8]) if len(item) > 8 else 0,
                    "net_inflow": float(item[9]) if len(item) > 9 else 0,
                    "stock_count": int(item[10]) if len(item) > 10 else 0,
                    "rise_count": int(item[11]) if len(item) > 11 else 0,
                    "fall_count": int(item[12]) if len(item) > 12 else 0,
                }
            )
        except (ValueError, IndexError, TypeError):
            continue

    if not records:
        raise ValueError("东方财富板块数据格式错误")

    df = pd.DataFrame(records)
    df = df[(df["sector_name"].astype(str).str.len() > 0) & (df["change_percent"].notna())]
    if df.empty:
        raise ValueError("东方财富无有效板块数据")
    return df


def _fetch_sector_data_from_eastmoney_push2_industry() -> Optional[pd.DataFrame]:
    """
    东方财富行业板块列表（push2 clist/get）。
    返回标准化 DataFrame：sector_name, change_percent, net_inflow(可缺省为 0)。
    """
    hosts = ["17.push2.eastmoney.com", "82.push2.eastmoney.com", "88.push2.eastmoney.com"]
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:90 t:2 f:!50",
        # 最小字段：f14 名称，f3 涨跌幅；f62 主力净流入（若不存在则为空）
        "fields": "f14,f3,f62",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/center/boardlist.html#industry_board"}

    last_err: Optional[Exception] = None
    for h in hosts:
        url = f"https://{h}/api/qt/clist/get"
        try:
            ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
            with ctx:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            j = resp.json()
            diff = (((j or {}).get("data") or {}).get("diff")) or []
            if not diff:
                continue
            rows: List[Dict[str, Any]] = []
            for it in diff:
                if not isinstance(it, dict):
                    continue
                name = str(it.get("f14") or "").strip()
                if not name:
                    continue
                try:
                    chg = float(it.get("f3") or 0.0)
                except Exception:
                    chg = 0.0
                try:
                    net = float(it.get("f62") or 0.0)
                except Exception:
                    net = 0.0
                rows.append({"sector_name": name, "change_percent": chg, "net_inflow": net})
            if not rows:
                continue
            return pd.DataFrame(rows)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue

    if last_err:
        logger.warning("eastmoney push2 industry board failed: %s", last_err)
    return None


def _fetch_sector_data_from_akshare(sector_type: str) -> Optional[pd.DataFrame]:
    """
    使用 AkShare 行业/概念板块接口作为备用源。
    仅保证提供 sector_name + change_percent（net_inflow 若不可得则为 0）。
    """
    try:
        import akshare as ak  # type: ignore[import]
    except Exception as e:  # noqa: BLE001
        logger.error(f"AkShare 未安装或导入失败: {e}")
        return None

    if sector_type != "industry":
        # 目前仅对 industry 提供备用源；concept 可后续扩展
        return None

    try:
        ctx = without_proxy_env() if PROXY_ENV_AVAILABLE else nullcontext()
        with ctx:
            df_raw = ak.stock_board_industry_name_em()
    except Exception as e:  # noqa: BLE001
        logger.error(f"AkShare 行业板块接口失败: {e}")
        return None

    if df_raw is None or df_raw.empty:
        return None

    df_raw = df_raw.copy()
    # 猜测/匹配列名：不同版本 AkShare 列名可能为「板块名称/名称/指数/涨跌幅/涨幅/涨跌幅%/主力净流入」等
    cols = {c: str(c) for c in df_raw.columns}
    name_col = None
    change_col = None
    net_col = None
    for c in df_raw.columns:
        s = str(c)
        if name_col is None and ("名称" in s or "板块" in s):
            name_col = c
        if change_col is None and ("涨跌幅" in s or "涨幅" in s):
            change_col = c
        if net_col is None and ("净流入" in s or "主力净流入" in s):
            net_col = c

    if name_col is None or change_col is None:
        logger.error("AkShare 行业板块数据缺少名称或涨跌幅列")
        return None

    df = pd.DataFrame(
        {
            "sector_name": df_raw[name_col],
            "change_percent": pd.to_numeric(df_raw[change_col], errors="coerce"),
            "net_inflow": pd.to_numeric(df_raw[net_col], errors="coerce") if net_col is not None else 0.0,
        }
    )
    df = df[(df["sector_name"].astype(str).str.len() > 0) & (df["change_percent"].notna())]
    if df.empty:
        return None
    return df


def _build_sector_response_from_df(
    df: pd.DataFrame,
    sector_type: str,
    *,
    data_source: Optional[str] = None,
) -> Dict:
    """从标准化 DataFrame 构建 tool_fetch_sector_data 返回结构。"""
    df = df.copy()
    df = df.sort_values("change_percent", ascending=False)
    df["rank"] = range(1, len(df) + 1)

    top_gainers = df.head(5).to_dict("records")
    top_losers = df.tail(5).to_dict("records")
    net_inflow_series = df["net_inflow"] if "net_inflow" in df.columns else pd.Series([0] * len(df))
    top_inflow = df.assign(net_inflow=net_inflow_series).sort_values("net_inflow", ascending=False).head(5).to_dict("records")

    rotation_speed = _calculate_rotation_speed(df)
    etf_recommendations = _generate_etf_recommendations(df.head(10))
    signal = _generate_sector_signal(df, rotation_speed)

    out: Dict = {
        "status": "success",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sector_type": sector_type,
        "summary": {
            "total_sectors": len(df),
            "avg_change": round(df["change_percent"].mean(), 2),
            "max_gain": round(df["change_percent"].max(), 2),
            "max_loss": round(df["change_percent"].min(), 2),
            "total_inflow": round(float(net_inflow_series.sum()), 2),
            "rotation_speed": rotation_speed,
        },
        "leaders": {
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "top_inflow": top_inflow,
        },
        "etf_recommendations": etf_recommendations,
        "signal": signal,
        "all_data": df.head(20).to_dict("records"),
    }
    if data_source:
        out["data_source"] = data_source
    return out


def _finalize_sector_response(
    df: pd.DataFrame,
    sector_type: str,
    source: str,
    cache_key: str,
    *,
    attempts: Optional[List[Dict[str, Any]]] = None,
) -> Dict:
    base = _build_sector_response_from_df(df, sector_type, data_source=source)
    top5_codes = [str(x.get("sector_name", "")) for x in base.get("leaders", {}).get("top_gainers", [])][:5]
    history = _TOP5_HISTORY.setdefault(sector_type, [])
    previous = history[-1] if history else []
    overlap = len(set(previous) & set(top5_codes)) if previous else 0
    rotation_speed_score = round(1 - overlap / 5, 4) if previous else 0.0
    history.append(top5_codes)
    if len(history) > 20:
        history.pop(0)
    main_line = top5_codes[0] if top5_codes else None
    gate = quality_gate_records(
        df.to_dict("records"),
        min_records=30 if sector_type == "industry" else 10,
        required_fields=["sector_name", "change_percent"],
    )
    fallback_route = [a["source"] for a in (attempts or []) if not a.get("ok")]
    as_of = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_gainers = base.get("leaders", {}).get("top_gainers", [])
    top_losers = base.get("leaders", {}).get("top_losers", [])
    total_count = int(base.get("summary", {}).get("total_sectors", 0))
    base["rotation_speed_score"] = rotation_speed_score
    base["main_line"] = main_line
    base["strong_days"] = {name: 1 for name in top5_codes}
    base["quality_gate"] = gate
    base["fallback_route"] = fallback_route
    base["as_of"] = as_of
    base["sectors"] = {
        sector_type: {
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "total_count": total_count,
            "quality_gate_passed": bool(gate.get("ok")),
        }
    }
    base["derived"] = {
        "rotation_speed_score": rotation_speed_score,
        "main_line": main_line,
        "signal": base.get("signal", {}),
    }
    base["metric_semantics"] = {
        "change_percent": "板块涨跌幅截面（百分比）",
        "net_inflow": "板块净流入（上游可得时）",
        "rotation_speed_score": "Top5 与上一快照重合率转换得分（1-重合占比）",
        "strong_days": "板块连续处于 Top5 的天数（当前版本为会话级）",
    }
    base["explanation"] = {
        "main_line_reason": f"主线板块为 {main_line}，基于当期涨跌幅 Top1 识别。" if main_line else "暂无可识别主线。",
        "rotation_speed_interpretation": f"Top5 相对上一快照重合 {overlap}/5，轮动得分 {rotation_speed_score}。",
        "signal_reason": "信号由市场强弱、轮动速度与风格因子共同生成。",
    }
    ttl = infer_ttl_seconds("sector")
    cache_set(cache_key, base, ttl)
    return normalize_contract(
        success=True,
        payload=base,
        source=source,
        attempts=attempts or [{"source": source, "ok": True, "message": "ok"}],
        used_fallback=bool(fallback_route),
        data_quality="fresh" if gate.get("ok") else "partial",
        cache_hit=False,
    )


def _calculate_rotation_speed(df: pd.DataFrame) -> str:
    """
    计算板块轮动速度
    
    Args:
        df: 板块数据DataFrame
    
    Returns:
        "slow" / "medium" / "fast"
    """
    # 计算涨幅方差
    variance = df["change_percent"].var()
    
    if variance > 15:
        return "fast"
    elif variance > 8:
        return "medium"
    else:
        return "slow"


def _generate_etf_recommendations(df: pd.DataFrame) -> List[Dict]:
    """
    根据板块表现生成ETF推荐
    
    Args:
        df: 前10个板块数据
    
    Returns:
        ETF推荐列表
    """
    # 板块到ETF映射
    sector_etf_map = {
        "计算机": "159999",  # 科技ETF
        "电子": "159999",  # 科技ETF
        "通信": "515880",  # 通信ETF
        "半导体": "512480",  # 半导体ETF
        "医药": "512010",  # 医药ETF
        "生物制品": "512010",  # 医药ETF
        "医疗服务": "512010",  # 医药ETF
        "食品饮料": "159928",  # 消费ETF
        "家用电器": "159928",  # 消费ETF
        "汽车": "512010",  # 医药ETF（暂时无汽车ETF，用医药代替）
        "电气设备": "515790",  # 光伏ETF
        "电力": "515790",  # 光伏ETF
        "银行": "512800",  # 银行ETF
        "非银金融": "512000",  # 券商ETF
        "房地产": "512200",  # 地产ETF
        "建筑材料": "512710",  # 建材ETF
        "国防军工": "512560",  # 军工ETF
        "有色金属": "512400",  # 有色ETF
        "化工": "515220",  # 化工ETF
        "机械设备": "159999",  # 科技ETF（暂时用）
    }
    
    recommendations = []
    seen_etfs = set()
    
    for _, row in df.iterrows():
        sector_name = row["sector_name"]
        
        # 查找对应的ETF
        for keyword, etf_code in sector_etf_map.items():
            if keyword in sector_name and etf_code not in seen_etfs:
                ni = float(row["net_inflow"]) if pd.notna(row.get("net_inflow", 0)) else 0.0
                recommendations.append({
                    "sector_name": sector_name,
                    "etf_code": etf_code,
                    "sector_change": round(float(row["change_percent"]), 2),
                    "sector_inflow": round(ni, 2),
                    "score": float(row["change_percent"]) * 0.4 + ni * 0.6,
                })
                seen_etfs.add(etf_code)
                break
        
        if len(recommendations) >= 3:  # 最多推荐3个ETF
            break
    
    # 按分数排序
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    
    return recommendations


def _generate_sector_signal(df: pd.DataFrame, rotation_speed: str) -> Dict:
    """
    生成板块信号
    
    Args:
        df: 板块数据
        rotation_speed: 轮动速度
    
    Returns:
        信号字典
    """
    # 计算市场强度
    avg_change = df["change_percent"].mean()
    positive_count = (df["change_percent"] > 0).sum()
    positive_ratio = positive_count / len(df) if len(df) > 0 else 0
    
    # 判断市场热度
    if avg_change > 1.5 and positive_ratio > 0.7:
        market_strength = "strong_bull"
        strength_desc = "强势牛市"
    elif avg_change > 0.5 and positive_ratio > 0.6:
        market_strength = "bull"
        strength_desc = "温和上涨"
    elif avg_change > -0.5 and positive_ratio > 0.4:
        market_strength = "neutral"
        strength_desc = "震荡市"
    elif avg_change > -2 and positive_ratio > 0.3:
        market_strength = "bear"
        strength_desc = "弱势下跌"
    else:
        market_strength = "strong_bear"
        strength_desc = "深度下跌"
    
    # 轮动速度判断
    if rotation_speed == "fast":
        rotation_desc = "快速轮动，适合短线"
        confidence = 0.7
    elif rotation_speed == "medium":
        rotation_desc = "中等轮动，适合波段"
        confidence = 0.8
    else:
        rotation_desc = "缓慢轮动，适合配置"
        confidence = 0.6
    
    # 风格判断
    top_sectors = df.head(3)
    tech_ratio = sum(1 for s in top_sectors["sector_name"] if "计算机" in s or "电子" in s or "通信" in s or "半导体" in s)
    
    if tech_ratio >= 2:
        style = "growth"
        style_desc = "成长风格"
        confidence = min(confidence + 0.1, 0.95)
    elif any("银行" in s or "保险" in s or "券商" in s for s in top_sectors["sector_name"]):
        style = "value"
        style_desc = "价值风格"
        confidence = confidence - 0.05
    else:
        style = "balanced"
        style_desc = "均衡配置"
    
    return {
        "market_strength": market_strength,
        "strength_description": strength_desc,
        "rotation_speed": rotation_speed,
        "rotation_description": rotation_desc,
        "style": style,
        "style_description": style_desc,
        "confidence": round(confidence, 2),
        "action": "积极布局" if market_strength in ["bull", "strong_bull"] else 
                 "谨慎操作" if market_strength == "neutral" else "观望等待"
    }


if __name__ == "__main__":
    # 测试
    result = tool_fetch_sector_data(sector_type="industry", period="today")
    print(json.dumps(result, indent=2, ensure_ascii=False))