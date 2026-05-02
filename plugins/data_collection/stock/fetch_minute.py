"""
获取A股股票分钟数据
在指数/ETF 分钟采集工具基础上实现，复用缓存与字段统一逻辑。
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
import pytz
import requests
import json
import time
import random
from contextlib import nullcontext

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

try:
    from mootdx.quotes import Quotes
    MOOTDX_AVAILABLE = True
except Exception:  # noqa: BLE001
    MOOTDX_AVAILABLE = False

try:
    import efinance as ef  # noqa: F401
    EFINANCE_AVAILABLE = True
except ImportError:
    EFINANCE_AVAILABLE = False


def _ensure_src_import():
    selected_root: Optional[Path] = None
    for parent in Path(__file__).resolve().parents:
        if (parent / "src").exists():
            selected_root = parent
            break
    if selected_root is not None and str(selected_root) not in sys.path:
        sys.path.insert(0, str(selected_root))
    return selected_root


_ROOT = _ensure_src_import()

try:
    from src.data_cache import (
        get_cached_stock_minute,
        save_stock_minute_cache,
        merge_cached_and_fetched_data,
    )
    from src.config_loader import load_system_config
    CACHE_AVAILABLE = True
except Exception:
    CACHE_AVAILABLE = False
    load_system_config = None  # type: ignore[arg-type]

# 交易日判断工具
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
utils_path = os.path.join(parent_dir, "utils")
if utils_path not in sys.path:
    sys.path.insert(0, utils_path)

try:
    from plugins.utils.trading_day import check_trading_day_before_operation
    TRADING_DAY_CHECK_AVAILABLE = True
except ImportError:
    TRADING_DAY_CHECK_AVAILABLE = False

    def check_trading_day_before_operation(*args, **kwargs):
        return None

try:
    from plugins.utils.proxy_env import without_proxy_env
    PROXY_ENV_AVAILABLE = True
except Exception:
    PROXY_ENV_AVAILABLE = False

    def without_proxy_env(*args, **kwargs):  # type: ignore[no-redef]
        return nullcontext()


# 最近一次 fetch_single_stock_minute 的调试信息（用于 mode=test 排障）
_LAST_FETCH_SINGLE_DEBUG: Dict[str, Any] = {}


_SINA_USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


def _pick_sina_user_agent() -> str:
    return random.choice(_SINA_USER_AGENT_POOL)


def _apply_delay_jitter(delay_seconds: float, jitter_ratio: float = 0.2) -> float:
    if delay_seconds <= 0:
        return 0.0
    jitter_amount = delay_seconds * jitter_ratio * (random.random() * 2 - 1)
    return max(0.0, delay_seconds + jitter_amount)


def _normalize_stock_code_for_sina(raw: str) -> Optional[str]:
    """
    Normalize stock code to 6-digit digits for sina symbol building.
    Accepts: 600751 / sh600751 / 600751.SH / 600751.SZ / 600751.BJ etc.
    """
    s = str(raw or "").strip()
    if not s:
        return None
    u = s.upper().replace("．", ".")
    for suf in (".SH", ".SZ", ".BJ"):
        if u.endswith(suf):
            u = u[: -len(suf)]
            break
    low = u.lower()
    if low.startswith(("sh", "sz", "bj")) and len(u) > 2:
        u = u[2:]
    u = u.strip()
    if not u.isdigit() or len(u) != 6:
        return None
    return u


def _stock_sina_symbol(digits: str) -> str:
    return f"sh{digits}" if digits.startswith("6") else f"sz{digits}"


def _fetch_stock_minute_sina_direct(
    stock_code: str,
    period: str,
    start_date_str: str,
    end_date_str: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Optional[pd.DataFrame]:
    """
    Direct Sina minute K-line fetch (more resilient than AkShare wrapper).
    Endpoint: https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData
    """
    clean = _normalize_stock_code_for_sina(stock_code)
    if not clean:
        return None
    sina_symbol = _stock_sina_symbol(clean)

    period_to_scale = {"1": 1, "5": 5, "15": 15, "30": 30, "60": 60}
    scale = period_to_scale.get(period)
    if scale is None:
        return None

    try:
        start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str[:10], "%Y-%m-%d")
        days_diff = (end_dt - start_dt).days + 1
        datalen = min(int(days_diff * (240 / scale) * 1.2), 1023)
    except Exception:
        datalen = 1023

    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": sina_symbol, "scale": scale, "ma": "no", "datalen": datalen}
    headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": _pick_sina_user_agent()}

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(_apply_delay_jitter(min(retry_delay * (2 ** (attempt - 1)), 20.0)))
                headers["User-Agent"] = _pick_sina_user_agent()

            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code != 200:
                continue

            try:
                data = r.json()
            except Exception:
                try:
                    data = json.loads(r.text)
                except Exception:
                    continue

            if not data or not isinstance(data, list):
                continue

            df = pd.DataFrame(data)
            if df is None or df.empty:
                continue

            column_mapping = {
                "day": "时间",
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
            }
            keep = [c for c in column_mapping.keys() if c in df.columns]
            if not keep:
                continue

            df = df[keep].copy().rename(columns=column_mapping)
            if "成交额" not in df.columns:
                df["成交额"] = 0.0

            if "时间" in df.columns:
                raw_time = df["时间"].copy()
                parsed = pd.to_datetime(df["时间"], errors="coerce")
                if parsed.notna().any():
                    df["时间"] = parsed
                    df = df[df["时间"].notna()].copy()
                    df["时间"] = df["时间"].dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    df["时间"] = raw_time.astype(str)

            for c in ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            df = normalize_column_names(df)
            df = calculate_missing_fields(df)

            if "时间" in df.columns:
                df = df.sort_values("时间").reset_index(drop=True)

            # Light end-date filtering only (avoid over-filtering to empty)
            try:
                end_dt2 = datetime.strptime(end_date_str[:19], "%Y-%m-%d %H:%M:%S")
                tvals = pd.to_datetime(df["时间"], errors="coerce")
                mask = tvals.notna() & (tvals <= end_dt2)
                df2 = df[mask].copy()
                if not df2.empty:
                    df = df2
            except Exception:
                pass

            return df if df is not None and not df.empty else None
        except Exception:
            continue

    return None


def normalize_date(date_str: str) -> str:
    """统一日期格式为 YYYY-MM-DD HH:MM:SS"""
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 09:30:00"
    if len(date_str) == 10 and "-" in date_str:
        return f"{date_str} 09:30:00"
    return date_str


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """统一字段名映射：将英文字段名转换为中文字段名"""
    if df is None or df.empty:
        return df

    column_mapping: Dict[str, str] = {}

    # 时间字段
    if "time" in df.columns and "时间" not in df.columns:
        column_mapping["time"] = "时间"
    if "date" in df.columns and "时间" not in df.columns:
        column_mapping["date"] = "时间"
    if "datetime" in df.columns and "时间" not in df.columns:
        column_mapping["datetime"] = "时间"
    if "day" in df.columns and "时间" not in df.columns:
        column_mapping["day"] = "时间"

    # 价格字段
    if "open" in df.columns and "开盘" not in df.columns:
        column_mapping["open"] = "开盘"
    if "close" in df.columns and "收盘" not in df.columns:
        column_mapping["close"] = "收盘"
    if "high" in df.columns and "最高" not in df.columns:
        column_mapping["high"] = "最高"
    if "low" in df.columns and "最低" not in df.columns:
        column_mapping["low"] = "最低"

    # 成交量字段
    if "volume" in df.columns and "成交量" not in df.columns:
        column_mapping["volume"] = "成交量"
    if "vol" in df.columns and "成交量" not in df.columns:
        column_mapping["vol"] = "成交量"

    # 成交额字段
    if "amount" in df.columns and "成交额" not in df.columns:
        column_mapping["amount"] = "成交额"

    if column_mapping:
        df = df.rename(columns=column_mapping)
    return df


def calculate_missing_fields(df: pd.DataFrame) -> pd.DataFrame:
    """自动计算缺失的成交额和涨跌幅"""
    if df is None or df.empty:
        return df

    df = df.copy()

    # AkShare/Sina 在部分 pandas 版本下可能把 volume 列为字符串 dtype；先数值化，避免成交额计算报错
    for col in ("开盘", "收盘", "最高", "最低", "成交量", "成交额"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "成交额" not in df.columns or df["成交额"].isna().all() or (df["成交额"] == 0).all():
        if "成交量" in df.columns and "收盘" in df.columns:
            df["成交额"] = df["成交量"] * df["收盘"] * 100
        else:
            df["成交额"] = 0

    if "涨跌幅" not in df.columns:
        if "收盘" in df.columns:
            df["涨跌幅"] = df["收盘"].pct_change() * 100
            df["涨跌幅"] = df["涨跌幅"].replace([np.inf, -np.inf], np.nan).fillna(0)
        else:
            df["涨跌幅"] = 0

    return df


def _get_latest_cached_timestamp_stock(
    symbol: str,
    period: str,
    date_yyyymmdd: str,
    config: Optional[Dict] = None,
) -> Optional[datetime]:
    """
    获取指定 symbol/period/date 的缓存中最新一条数据的时间戳。
    用于判断缓存新鲜度：若 (当前时间 - 最新时间) > period 分钟，则需要拉取。
    """
    if not CACHE_AVAILABLE:
        return None
    try:
        cached_df, missing = get_cached_stock_minute(
            symbol, period, date_yyyymmdd, date_yyyymmdd, config=config
        )
        if cached_df is None or cached_df.empty:
            return None
        time_col = None
        for col in ["时间", "date", "日期时间", "datetime"]:
            if col in cached_df.columns:
                time_col = col
                break
        if not time_col:
            return None
        last_val = cached_df[time_col].iloc[-1]
        if pd.isna(last_val):
            return None
        dt = pd.to_datetime(last_val)
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()
        tz_sh = pytz.timezone("Asia/Shanghai")
        if dt.tzinfo is None:
            dt = tz_sh.localize(dt)
        elif str(dt.tzinfo) != "Asia/Shanghai":
            dt = dt.astimezone(tz_sh)
        return dt
    except Exception:
        return None


def _fetch_stock_minute_sina(
    stock_code: str,
    period: str,
    start_date_str: str,
    end_date_str: str,
) -> Optional[pd.DataFrame]:
    """
    使用 AkShare 的新浪分钟接口获取股票分钟数据（主数据源）
    对应 docs 中的 stock_zh_a_minute(symbol='sh600751', period='1', adjust="qfq")
    备注：在部分环境/时段下 adjust="" 可能返回空；这里做多路尝试提高命中率。
    """
    if not AKSHARE_AVAILABLE:
        return None
    # 构造带交易所前缀的 symbol
    clean = stock_code
    if clean.upper().endswith((".SH", ".SZ", ".BJ")):
        clean = clean.split(".")[0]
    if clean.lower().startswith(("sh", "sz", "bj")) and len(clean) > 2:
        clean = clean[2:]
    if clean.startswith("6"):
        symbol = f"sh{clean}"
    else:
        symbol = f"sz{clean}"
    for adj in ("qfq", "", "hfq"):
        try:
            # 先按当前环境请求（有些环境需要代理/自定义网络）
            df = ak.stock_zh_a_minute(symbol=symbol, period=period, adjust=adj)
            # 若为空，再尝试临时清理代理环境（避免代理导致的偶发异常/污染）
            if (df is None or df.empty) and PROXY_ENV_AVAILABLE:
                with without_proxy_env():
                    df = ak.stock_zh_a_minute(symbol=symbol, period=period, adjust=adj)
            if df is None or df.empty:
                continue
            # stock_zh_a_minute 返回列名为 day/open/high/low/close/volume/amount
            df = normalize_column_names(df)
            df = calculate_missing_fields(df)
            if "时间" in df.columns:
                # 仅当能解析出有效时间时才过滤；否则保留原始字符串避免整表变空
                raw_time = df["时间"].copy()
                parsed = pd.to_datetime(df["时间"], errors="coerce")
                if parsed.notna().any():
                    df["时间"] = parsed
                    df = df[df["时间"].notna()].copy()
                    df["时间"] = df["时间"].dt.strftime("%Y-%m-%d %H:%M:%S")
                    df = df.sort_values("时间").reset_index(drop=True)
                else:
                    df["时间"] = raw_time.astype(str)
            return df
        except Exception:
            continue
    return None


def _fetch_stock_minute_efinance(
    clean_code: str,
    period: str,
    start_date_str: str,
    end_date_str: str,
) -> Optional[pd.DataFrame]:
    """
    efinance 东财路径，作为 AkShare 双路由均失败后的第四 Provider。
    klt：1/5/15/30/60 分钟（与 efinance 文档一致）。
    """
    if not EFINANCE_AVAILABLE:
        return None
    try:
        import efinance as ef
    except ImportError:
        return None
    klt_map = {"1": 1, "5": 5, "15": 15, "30": 30, "60": 60}
    klt = klt_map.get(period)
    if klt is None:
        return None
    beg = start_date_str[:10].replace("-", "")
    end = end_date_str[:10].replace("-", "")
    try:
        df = ef.stock.get_quote_history(
            stock_codes=clean_code,
            beg=beg,
            end=end,
            klt=klt,
            fqt=1,
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = df.copy()
    time_col = None
    for c in df.columns:
        if str(c) in ("时间", "日期"):
            time_col = c
            break
    if time_col is None:
        return None
    if time_col != "时间":
        df = df.rename(columns={time_col: "时间"})
    df = normalize_column_names(df)
    df = calculate_missing_fields(df)
    if "时间" in df.columns:
        df["时间"] = pd.to_datetime(df["时间"], errors="coerce")
        df = df[df["时间"].notna()].copy()
        df["时间"] = df["时间"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df = df.sort_values("时间").reset_index(drop=True)
    return df


def _fetch_stock_minute_eastmoney(
    clean_code: str,
    period: str,
    start_date_str: str,
    end_date_str: str,
) -> Optional[pd.DataFrame]:
    """
    使用 AkShare 的东财分钟接口获取股票分钟数据（备用数据源）
    对应 docs 中的 stock_zh_a_hist_min_em
    """
    def _normalize_out(df: pd.DataFrame) -> Optional[pd.DataFrame]:
        if df is None or df.empty:
            return None
        df = normalize_column_names(df)
        df = calculate_missing_fields(df)
        if "时间" in df.columns:
            raw_time = df["时间"].copy()
            parsed = pd.to_datetime(df["时间"], errors="coerce")
            if parsed.notna().any():
                df["时间"] = parsed
                df = df[df["时间"].notna()].copy()
                df["时间"] = df["时间"].dt.strftime("%Y-%m-%d %H:%M:%S")
                df = df.sort_values("时间").reset_index(drop=True)
            else:
                df["时间"] = raw_time.astype(str)
        return df if df is not None and not df.empty else None

    # 1) 先尝试 AkShare（若可用）
    if AKSHARE_AVAILABLE:
        try:
            df = ak.stock_zh_a_hist_min_em(
                symbol=clean_code,
                period=period,
                start_date=start_date_str,
                end_date=end_date_str,
                adjust="",
            )
            if (df is None or df.empty) and PROXY_ENV_AVAILABLE:
                with without_proxy_env():
                    df = ak.stock_zh_a_hist_min_em(
                        symbol=clean_code,
                        period=period,
                        start_date=start_date_str,
                        end_date=end_date_str,
                        adjust="",
                    )
            out = _normalize_out(df)
            if out is not None:
                return out
        except Exception:
            pass

    # 2) 兜底：直连东财 push2his（避免 akshare 偶发断连）
    try:
        # secid market_id: 1 上证 0 深证
        market_id = 1 if str(clean_code).startswith("6") else 0
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": period,
            "fqt": "0",
            "secid": f"{market_id}.{clean_code}",
            "beg": "0",
            "end": "20500000",
        }
        r = requests.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if (r is None or r.status_code >= 400) and PROXY_ENV_AVAILABLE:
            with without_proxy_env():
                r = requests.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        j = r.json()
        kl = ((j or {}).get("data") or {}).get("klines") or []
        if not kl:
            return None
        rows = [x.split(",") for x in kl if isinstance(x, str) and x]
        if not rows:
            return None
        df2 = pd.DataFrame(rows)
        # f51..f58 => 时间,开盘,收盘,最高,最低,成交量,成交额,振幅
        if df2.shape[1] < 7:
            return None
        df2 = df2.iloc[:, :7]
        df2.columns = ["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
        for c in ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]:
            df2[c] = pd.to_numeric(df2[c], errors="coerce")
        out = _normalize_out(df2)
        return out
    except Exception:
        return None


def _fetch_stock_minute_mootdx(
    stock_code: str,
    period: str,
    start_date_str: str,
    end_date_str: str,
    max_bars: int = 800,
) -> Optional[pd.DataFrame]:
    """
    使用 mootdx 获取股票分钟数据。

    参数:
        stock_code: 可以是 600519 / sh600519 / 600519.SH 等，会在内部标准化为6位代码
        period: "1", "5", "15", "30", "60"
        start_date_str/end_date_str: "YYYY-MM-DD HH:MM:SS"
    """
    if not MOOTDX_AVAILABLE:
        return None

    clean = stock_code
    if clean.upper().endswith((".SH", ".SZ", ".BJ")):
        clean = clean.split(".")[0]
    if clean.lower().startswith(("sh", "sz", "bj")) and len(clean) > 2:
        clean = clean[2:]

    freq_map = {
        "1": 7,   # 1 分钟
        "5": 0,   # 5 分钟
        "15": 1,  # 15 分钟
        "30": 2,  # 30 分钟
        "60": 3,  # 60 分钟
    }
    frequency = freq_map.get(period)
    if frequency is None:
        return None

    try:
        client = Quotes.factory(market="std")
    except Exception:
        return None

    try:
        df = client.bars(symbol=clean, frequency=frequency, offset=max_bars)
    except Exception:
        return None

    if df is None or df.empty:
        return None

    df = df.copy()

    # mootdx 返回字段: datetime/open/high/low/close/vol/amount 等
    if "datetime" in df.columns and "时间" not in df.columns:
        df["时间"] = pd.to_datetime(df["datetime"], errors="coerce")

    df = normalize_column_names(df)
    df = calculate_missing_fields(df)

    if "时间" in df.columns:
        try:
            df["时间"] = pd.to_datetime(df["时间"], errors="coerce")
            df = df[df["时间"].notna()].copy()
            df["时间"] = df["时间"].dt.strftime("%Y-%m-%d %H:%M:%S")

            start_dt = datetime.strptime(start_date_str[:19], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_date_str[:19], "%Y-%m-%d %H:%M:%S")

            time_vals = pd.to_datetime(df["时间"], errors="coerce")
            mask = (time_vals >= start_dt) & (time_vals <= end_dt)
            df = df[mask].copy()
        except Exception:
            pass

    if df.empty:
        return None

    return df


def fetch_single_stock_minute(
    stock_code: str,
    period: str = "5",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 5,
    use_cache: bool = True,
    minute_source_preference: str = "auto",
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    获取单只股票的分钟数据。

    minute_source_preference: auto | sina | eastmoney | efinance
    在 mootdx 之后按此顺序尝试 AkShare/efinance 路由（默认与现网一致：新浪 → 东财 → efinance）。
    """
    if period not in ["1", "5", "15", "30", "60"]:
        return None, None

    clean_code = stock_code
    if clean_code.upper().endswith((".SH", ".SZ", ".BJ")):
        clean_code = clean_code.split(".")[0]
    if clean_code.lower().startswith(("sh", "sz", "bj")) and len(clean_code) > 2:
        clean_code = clean_code[2:]

    now = datetime.now()
    if not end_date:
        end_date_str = now.strftime("%Y-%m-%d 15:00:00")
    else:
        end_date_str = normalize_date(end_date)
        if not end_date_str.endswith(" 15:00:00"):
            end_date_str = end_date_str.replace(" 09:30:00", " 15:00:00")

    if not start_date:
        start = now - timedelta(days=lookback_days * 2)
        start_date_str = start.strftime("%Y-%m-%d 09:30:00")
    else:
        start_date_str = normalize_date(start_date)

    df: Optional[pd.DataFrame] = None
    source: Optional[str] = None
    cached_partial_df: Optional[pd.DataFrame] = None
    debug: Dict[str, Any] = {
        "stock_code": stock_code,
        "clean_code": clean_code,
        "period": period,
        "start_date_str": start_date_str,
        "end_date_str": end_date_str,
        "minute_source_preference": minute_source_preference,
        "attempts": [],
    }

    # 缓存
    if use_cache and CACHE_AVAILABLE:
        try:
            config = load_system_config(use_cache=True) if load_system_config else None
            start_date_formatted = start_date_str[:10].replace("-", "")
            end_date_formatted = end_date_str[:10].replace("-", "")
            cached_df, missing_dates = get_cached_stock_minute(
                clean_code, period, start_date_formatted, end_date_formatted, config=config
            )
            if cached_df is not None and not cached_df.empty and not missing_dates:
                return cached_df, "cache"
            if cached_df is not None and not cached_df.empty and missing_dates:
                cached_partial_df = cached_df
                if missing_dates:
                    start_date_formatted = min(missing_dates)
                    end_date_formatted = max(missing_dates)
                    start_date_str = f"{start_date_formatted[:4]}-{start_date_formatted[4:6]}-{start_date_formatted[6:8]} 09:30:00"
                    end_date_str = f"{end_date_formatted[:4]}-{end_date_formatted[4:6]}-{end_date_formatted[6:8]} 15:00:00"
        except Exception:
            pass

    # 主数据源1：mootdx 分钟K线（如果可用）
    try:
        debug["attempts"].append({"source": "mootdx", "ok": False})
        df = _fetch_stock_minute_mootdx(
            stock_code=stock_code,
            period=period,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )
        if df is not None and not df.empty:
            source = "mootdx"
            debug["attempts"][-1]["ok"] = True
    except Exception as e:  # noqa: BLE001
        debug["attempts"][-1]["error"] = repr(e)

    pref = (minute_source_preference or "auto").strip().lower()
    if pref not in ("auto", "sina", "eastmoney", "efinance"):
        pref = "auto"

    def _try_sina() -> None:
        nonlocal df, source
        # Prefer AkShare-based Sina fetch when available (more stable contract and aligns with tests),
        # then fall back to direct HTTP implementation.
        if (df is None or df.empty) and AKSHARE_AVAILABLE:
            debug["attempts"].append({"source": "sina_akshare", "ok": False})
            try:
                tmp = _fetch_stock_minute_sina(
                    stock_code=stock_code,
                    period=period,
                    start_date_str=start_date_str,
                    end_date_str=end_date_str,
                )
                if tmp is not None and not tmp.empty:
                    df = tmp
                    source = "sina_akshare"
                    debug["attempts"][-1]["ok"] = True
            except Exception as e:  # noqa: BLE001
                debug["attempts"][-1]["error"] = repr(e)

        if df is None or df.empty:
            debug["attempts"].append({"source": "sina_http", "ok": False})
            try:
                tmp = _fetch_stock_minute_sina_direct(
                    stock_code=stock_code,
                    period=period,
                    start_date_str=start_date_str,
                    end_date_str=end_date_str,
                )
                if tmp is not None and not tmp.empty:
                    df = tmp
                    source = "sina_http"
                    debug["attempts"][-1]["ok"] = True
                    return
            except Exception as e:  # noqa: BLE001
                debug["attempts"][-1]["error"] = repr(e)

    def _try_em() -> None:
        nonlocal df, source
        if (df is None or df.empty) and AKSHARE_AVAILABLE:
            debug["attempts"].append({"source": "eastmoney_akshare", "ok": False})
            try:
                tmp = _fetch_stock_minute_eastmoney(
                    clean_code=clean_code,
                    period=period,
                    start_date_str=start_date_str,
                    end_date_str=end_date_str,
                )
                if tmp is not None and not tmp.empty:
                    df = tmp
                    source = "eastmoney_akshare"
                    debug["attempts"][-1]["ok"] = True
            except Exception as e:  # noqa: BLE001
                debug["attempts"][-1]["error"] = repr(e)

    def _try_ef() -> None:
        nonlocal df, source
        if (df is None or df.empty) and EFINANCE_AVAILABLE:
            debug["attempts"].append({"source": "efinance", "ok": False})
            try:
                tmp = _fetch_stock_minute_efinance(
                    clean_code=clean_code,
                    period=period,
                    start_date_str=start_date_str,
                    end_date_str=end_date_str,
                )
                if tmp is not None and not tmp.empty:
                    df = tmp
                    source = "efinance"
                    debug["attempts"][-1]["ok"] = True
            except Exception as e:  # noqa: BLE001
                debug["attempts"][-1]["error"] = repr(e)

    if pref == "auto":
        _try_sina()
        _try_em()
        _try_ef()
    elif pref == "sina":
        _try_sina()
        _try_em()
        _try_ef()
    elif pref == "eastmoney":
        _try_em()
        _try_sina()
        _try_ef()
    else:  # efinance
        _try_ef()
        _try_sina()
        _try_em()

    # 合并部分缓存
    if df is not None and not df.empty and cached_partial_df is not None:
        try:
            time_col = None
            for col in ["时间", "date", "日期时间", "datetime"]:
                if col in df.columns:
                    time_col = col
                    break
            if time_col:
                df = merge_cached_and_fetched_data(cached_partial_df, df, time_col)
                source = f"{source}+cache" if source else "cache"
        except Exception:
            pass

    # 如果外部数据源失败但有部分缓存，返回缓存
    if (df is None or df.empty) and cached_partial_df is not None and not cached_partial_df.empty:
        df = cached_partial_df
        if not source:
            source = "cache_partial"

    # 保存缓存
    if df is not None and not df.empty and use_cache and CACHE_AVAILABLE:
        try:
            config = load_system_config(use_cache=True) if load_system_config else None
            save_stock_minute_cache(clean_code, period, df, config=config)
        except Exception:
            pass

    global _LAST_FETCH_SINGLE_DEBUG
    _LAST_FETCH_SINGLE_DEBUG = debug
    return df, source


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and (value != value)):
            return default
        if isinstance(value, (np.integer, np.floating)):
            return float(value)
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or (isinstance(value, float) and (value != value)):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fetch_stock_minute(
    stock_code: str = "600000",
    period: str = "5",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 5,
    mode: str = "production",
    use_cache: bool = True,
    minute_source_preference: str = "auto",
) -> Dict[str, Any]:
    """
    获取股票分钟数据，支持多股票代码（逗号分隔）
    """
    # 交易日检查
    if TRADING_DAY_CHECK_AVAILABLE and mode != "test":
        trading_day_check = check_trading_day_before_operation("获取股票分钟数据")
        if trading_day_check:
            return trading_day_check

    if period not in ["1", "5", "15", "30", "60", "5,15,30", "all"]:
        return {
            "success": False,
            "message": f"不支持的周期: {period}，支持: 1, 5, 15, 30, 60, 5,15,30, all",
            "data": None,
        }

    # 批量多周期采集模式：仅更新缓存，不返回明细
    if period in ("5,15,30", "all"):
        periods_to_fetch = ["5", "15", "30"]
        tz_sh = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz_sh)
        today = now.strftime("%Y%m%d")
        config = None
        if CACHE_AVAILABLE and load_system_config:
            try:
                config = load_system_config(use_cache=True)
            except Exception:
                config = None
        fetched: List[str] = []
        skipped: List[str] = []

        if isinstance(stock_code, str):
            codes = [c.strip() for c in stock_code.split(",") if c.strip()]
        else:
            codes = [str(stock_code).strip()]

        if not codes:
            return {"success": False, "message": "未提供有效的股票代码", "data": None}

        for code in codes:
            clean_code = code
            if clean_code.upper().endswith((".SH", ".SZ", ".BJ")):
                clean_code = clean_code.split(".")[0]
            if clean_code.lower().startswith(("sh", "sz", "bj")) and len(clean_code) > 2:
                clean_code = clean_code[2:]

            for p in periods_to_fetch:
                latest_ts = (
                    _get_latest_cached_timestamp_stock(clean_code, p, today, config)
                    if CACHE_AVAILABLE
                    else None
                )
                need_fetch = latest_ts is None
                if not need_fetch and latest_ts is not None:
                    gap_min = (now - latest_ts).total_seconds() / 60
                    need_fetch = gap_min > int(p)
                if need_fetch:
                    df_out, _ = fetch_single_stock_minute(
                        stock_code=clean_code,
                        period=p,
                        start_date=None,
                        end_date=None,
                        lookback_days=lookback_days or 5,
                        use_cache=use_cache,
                        minute_source_preference=minute_source_preference,
                    )
                    if df_out is not None and not df_out.empty:
                        fetched.append(f"{clean_code}/{p}min")
                    else:
                        skipped.append(f"{clean_code}/{p}min(fetch_failed)")
                else:
                    skipped.append(f"{clean_code}/{p}min")

        return {
            "success": True,
            "message": "批量采集完成，股票分钟数据已缓存",
            "data": {"fetched": fetched, "skipped": skipped},
        }

    # 单周期模式，返回 klines
    if isinstance(stock_code, str):
        codes = [c.strip() for c in stock_code.split(",") if c.strip()]
    elif isinstance(stock_code, list):
        codes = [str(c).strip() for c in stock_code if str(c).strip()]
    else:
        codes = [str(stock_code).strip()]

    if not codes:
        return {"success": False, "message": "未提供有效的股票代码", "data": None}

    now = datetime.now()
    if end_date:
        end_date_norm = normalize_date(end_date)[:10]
    else:
        end_date_norm = now.strftime("%Y-%m-%d")
    if start_date:
        start_date_norm = normalize_date(start_date)[:10]
    else:
        start = now - timedelta(days=lookback_days * 2)
        start_date_norm = start.strftime("%Y-%m-%d")

    results: List[Dict[str, Any]] = []
    source: Optional[str] = None
    debug_all: Dict[str, Any] = {"per_code": {}}

    for code in codes:
        df, data_source = fetch_single_stock_minute(
            stock_code=code,
            period=period,
            start_date=start_date_norm,
            end_date=end_date_norm,
            lookback_days=lookback_days,
            use_cache=use_cache,
            minute_source_preference=minute_source_preference,
        )
        if data_source:
            source = data_source
        if mode == "test":
            debug_all["per_code"][code] = dict(_LAST_FETCH_SINGLE_DEBUG)

        # 盘后/非交易日场景：如果默认区间（到“今天”）取不到分钟数据，尝试回退到最近一天
        if (df is None or df.empty) and not start_date and not end_date:
            try:
                end_dt = datetime.strptime(end_date_norm, "%Y-%m-%d")
                fallback_end = (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                fallback_start = (end_dt - timedelta(days=max(2, lookback_days))).strftime("%Y-%m-%d")
                df2, data_source2 = fetch_single_stock_minute(
                    stock_code=code,
                    period=period,
                    start_date=fallback_start,
                    end_date=fallback_end,
                    lookback_days=lookback_days,
                    use_cache=use_cache,
                    minute_source_preference=minute_source_preference,
                )
                if df2 is not None and not df2.empty:
                    df = df2
                    if data_source2:
                        source = data_source2
            except Exception:
                pass

        if df is None or df.empty:
            results.append(
                {
                    "stock_code": code,
                    "period": period,
                    "count": 0,
                    "klines": [],
                    "message": "股票分钟数据暂时不可用，请稍后重试",
                }
            )
            continue

        MAX_RECORDS = 350
        total_count = len(df)
        if total_count > MAX_RECORDS:
            df = df.tail(MAX_RECORDS).copy()

        klines: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            time_str = ""
            for col in ["时间", "日期", "date", "日期时间", "datetime"]:
                if col in row.index:
                    try:
                        v = row[col]
                        if hasattr(v, "strftime"):
                            time_str = v.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            time_str = str(v)
                        break
                    except Exception:
                        continue

            klines.append(
                {
                    "time": time_str,
                    "open": _safe_float(row.get("开盘")),
                    "close": _safe_float(row.get("收盘")),
                    "high": _safe_float(row.get("最高")),
                    "low": _safe_float(row.get("最低")),
                    "volume": _safe_int(row.get("成交量")),
                    "amount": _safe_float(row.get("成交额")),
                    "change_percent": _safe_float(row.get("涨跌幅")),
                }
            )

        result_data: Dict[str, Any] = {
            "stock_code": code,
            "period": period,
            "total_count": total_count,
            "returned_count": len(klines),
            "klines": klines,
            "start_date": start_date_norm,
            "end_date": end_date_norm,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if total_count > len(klines):
            result_data["note"] = f"共获取{total_count}条数据，只返回最新的{len(klines)}条"

        results.append(result_data)

    if not results:
        return {
            "success": False,
            "message": "未获取到任何数据",
            "data": None,
            "source": source or "unknown",
            "count": 0,
        }

    final_data: Any = results[0] if len(results) == 1 else results
    returned_total = 0
    try:
        returned_total = sum(int(r.get("returned_count", r.get("count", 0)) or 0) for r in results)
    except Exception:
        returned_total = 0

    if returned_total <= 0:
        out = {
            "success": False,
            "message": "未从外部源获取到分钟数据（returned_count=0）",
            "data": final_data,
            "source": source or "unknown",
            "count": len(results),
        }
        if mode == "test":
            out["debug"] = debug_all
        return out

    out = {
        "success": True,
        "message": f"Successfully fetched {returned_total} records",
        "data": final_data,
        "source": source or "akshare",
        "count": len(results),
    }
    if mode == "test":
        out["debug"] = debug_all
    return out


def tool_fetch_stock_minute(
    stock_code: str = "600000",
    period: str = "5",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 5,
    mode: str = "production",
    use_cache: bool = True,
    minute_source_preference: str = "auto",
) -> Dict[str, Any]:
    """
    OpenClaw 工具：获取股票分钟数据
    """
    return fetch_stock_minute(
        stock_code=stock_code,
        period=period,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
        mode=mode,
        use_cache=use_cache,
        minute_source_preference=minute_source_preference,
    )

