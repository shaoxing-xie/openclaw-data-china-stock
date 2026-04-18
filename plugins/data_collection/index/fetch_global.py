"""
获取全球指数最新快照（各交易所延迟不一，非毫秒级「实时」）
融合 Coze 插件 get_index_global_spot.py
OpenClaw 插件工具

数据源优先级（默认，可由 config 覆盖）：
1. yfinance (Yahoo Finance)
2. Financial Modeling Prep stable/quote（需 API key，见 data_sources.global_index.latest.fmp 或环境变量）
3. 新浪 hq.sinajs.cn：兜底，易 403/502
"""

import os
import re
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# 默认使用 yfinance 符号（雅虎财经标准）
DEFAULT_SYMBOLS_YF = ["^DJI", "^IXIC", "^GSPC", "^N225", "^HSI"]
# 新浪旧代码 -> yfinance 符号（兼容旧参数）
SINA_TO_YF = {
    "int_dji": "^DJI",
    "int_nasdaq": "^IXIC",
    "int_sp500": "^GSPC",
    "int_nikkei": "^N225",
    "rt_hkHSI": "^HSI",
    "int_hs": "^HSI",
    "rt_hk": "^HSI",
}
# yfinance 符号 -> 新浪 list 代码（兜底用）
YF_TO_SINA = {
    "^DJI": "int_dji",
    "^IXIC": "int_nasdaq",
    "^GSPC": "int_sp500",
    "^N225": "int_nikkei",
    "^HSI": "rt_hkHSI",
}
SINA_CODE_TO_YF = {v: k for k, v in YF_TO_SINA.items()}
# 指数名称（用于展示）
SYMBOL_NAME_MAP = {
    "^DJI": "道琼斯",
    "^IXIC": "纳斯达克",
    "^GSPC": "标普500",
    "^N225": "日经225",
    "^HSI": "恒生指数",
}

FMP_QUOTE_URL = "https://financialmodelingprep.com/stable/quote"

# 兼容：保留旧常量名供外部引用（默认指数代码列表）
DEFAULT_CODES = DEFAULT_SYMBOLS_YF.copy()
CODE_NAME_MAP = SYMBOL_NAME_MAP


def _normalize_codes(index_codes: Optional[str]) -> List[str]:
    """将用户输入的 index_codes 转为 yfinance 符号列表。"""
    if not index_codes:
        return DEFAULT_SYMBOLS_YF.copy()
    if isinstance(index_codes, list):
        raw = [str(c).strip() for c in index_codes if str(c).strip()]
    else:
        raw = [c.strip() for c in str(index_codes).split(",") if c.strip()]
    if not raw:
        return DEFAULT_SYMBOLS_YF.copy()
    out = []
    for c in raw:
        if c in SINA_TO_YF:
            out.append(SINA_TO_YF[c])
        elif c.startswith("^") or (len(c) <= 6 and c.isalnum()):
            out.append(c)
        else:
            out.append(SINA_TO_YF.get(c, c))
    return out if out else DEFAULT_SYMBOLS_YF.copy()


def _load_global_latest_config() -> Dict[str, Any]:
    """读取 data_sources.global_index.latest（不存在则返回默认）。"""
    try:
        from src.config_loader import load_system_config

        config = load_system_config(use_cache=True)
    except Exception:
        config = {}
    ds = config.get("data_sources") or {}
    gi = ds.get("global_index") or {}
    latest = gi.get("latest") or {}
    fmp = latest.get("fmp") or {}
    priority = latest.get("priority")
    if not priority:
        priority = ["yfinance", "fmp", "sina"]
    return {"fmp": fmp, "priority": priority}


def _resolve_fmp_api_keys(fmp_cfg: Dict[str, Any]) -> List[str]:
    """
    合并 YAML 中的 api_keys / api_key 与裸环境变量，去重保序。
    """
    keys: List[str] = []
    raw_list = fmp_cfg.get("api_keys")
    if isinstance(raw_list, list):
        for x in raw_list:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                keys.append(s)
    if not keys:
        ak = fmp_cfg.get("api_key")
        if isinstance(ak, str) and ak.strip():
            if "\n" in ak:
                for line in ak.splitlines():
                    s = line.strip()
                    if s:
                        keys.append(s)
            else:
                keys.append(ak.strip())
    if not keys:
        for env_name in ("FMP_API_KEY", "FMP_API_KEY_BACKUP", "FINANCIAL_MODELING_PREP_API_KEY"):
            v = os.getenv(env_name, "").strip()
            if v:
                keys.append(v)
    seen = set()
    out_keys: List[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out_keys.append(k)
    return out_keys


def _fmp_ts_to_str(ts: Any) -> str:
    if ts is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        t = int(ts)
        return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fetch_fmp_one_symbol(sym: str, api_keys: List[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """单 symbol 多 key 尝试。返回 (行数据, 最后一类错误文案)。"""
    import requests

    last_err: Optional[str] = None
    encoded = urllib.parse.quote(sym, safe="")
    for key in api_keys:
        url = f"{FMP_QUOTE_URL}?symbol={encoded}&apikey={key}"
        try:
            r = requests.get(url, timeout=18)
            text = r.text
            if r.status_code == 429:
                last_err = "HTTP 429"
                continue
            try:
                j = r.json()
            except Exception:
                last_err = "invalid json"
                continue
        except Exception as e:
            last_err = str(e)
            continue

        if isinstance(j, dict) and j.get("error"):
            err = str(j["error"])
            el = err.lower()
            if "limit" in el and ("api" in el or "remaining" in el):
                last_err = err
                continue
            if "premium" in el or "subscription" in el or "not available" in el:
                last_err = err
                break
            last_err = err
            break

        row_obj: Optional[Dict[str, Any]] = None
        if isinstance(j, list) and j:
            row_obj = j[0] if isinstance(j[0], dict) else None
        elif isinstance(j, dict) and "symbol" in j:
            row_obj = j

        if not row_obj:
            last_err = "empty quote"
            continue

        price = row_obj.get("price")
        if price is None:
            last_err = "no price"
            continue

        chg_pct = row_obj.get("changePercentage")
        chg = row_obj.get("change")
        name = row_obj.get("name") or SYMBOL_NAME_MAP.get(sym, sym)
        ts = _fmp_ts_to_str(row_obj.get("timestamp"))

        return {
            "code": row_obj.get("symbol") or sym,
            "name": name,
            "price": float(price) if price is not None else None,
            "change": float(chg) if chg is not None else None,
            "change_pct": round(float(chg_pct), 4) if chg_pct is not None else None,
            "timestamp": ts,
        }, None

    return None, last_err


def _fetch_fmp(symbols: List[str], api_keys: List[str]) -> Dict[str, Any]:
    """FMP quote，按 symbol 顺序返回能拿到的行。"""
    if not api_keys:
        return {"success": False, "data": [], "message": "未配置 FMP API key（data_sources.global_index.latest.fmp 或 FMP_API_KEY）"}
    data_list: List[Dict[str, Any]] = []
    errors: List[str] = []
    for sym in symbols:
        row, err = _fetch_fmp_one_symbol(sym, api_keys)
        if row:
            data_list.append(row)
        elif err:
            errors.append(f"{sym}:{err}")
    return {
        "success": len(data_list) > 0,
        "data": data_list,
        "source": "financialmodelingprep.com/stable/quote",
        "message": "; ".join(errors) if errors else None,
    }


def _fetch_yfinance(symbols: List[str]) -> Dict[str, Any]:
    """使用 yfinance 拉取全球指数；多标的时优先 batch download。"""
    try:
        import yfinance as yf
    except ImportError:
        return {"success": False, "data": [], "message": "未安装 yfinance"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if len(symbols) > 1:
        try:
            tickers = " ".join(symbols)
            df = yf.download(
                tickers,
                period="5d",
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
            )
            if df is not None and not df.empty and hasattr(df.columns, "levels"):
                data_list: List[Dict[str, Any]] = []
                for sym in symbols:
                    try:
                        if sym not in df.columns.get_level_values(0):
                            continue
                        close = df[sym]["Close"].dropna()
                        if close is None or len(close) < 1:
                            continue
                        price = float(close.iloc[-1])
                        prev = float(close.iloc[-2]) if len(close) >= 2 else price
                        change = price - prev if len(close) >= 2 else None
                        change_pct = (change / prev * 100) if (prev and prev != 0 and change is not None) else None
                        data_list.append({
                            "code": sym,
                            "name": SYMBOL_NAME_MAP.get(sym, sym),
                            "price": price,
                            "change": change,
                            "change_pct": round(change_pct, 4) if change_pct is not None else None,
                            "timestamp": now,
                        })
                    except Exception:
                        continue
                if data_list:
                    return {"success": True, "data": data_list, "source": "yfinance"}
        except Exception:
            pass

    data_list = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if hist is None or hist.empty:
                info = t.info
                price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
                change = info.get("regularMarketChange")
                change_pct = info.get("regularMarketChangePercent")
                name = info.get("shortName") or info.get("longName") or SYMBOL_NAME_MAP.get(sym, sym)
            else:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
                change = price - prev if len(hist) >= 2 else None
                change_pct = (change / prev * 100) if (prev and prev != 0 and change is not None) else None
                name = SYMBOL_NAME_MAP.get(sym, sym)
            data_list.append({
                "code": sym,
                "name": name,
                "price": price,
                "change": change,
                "change_pct": round(change_pct, 4) if change_pct is not None else None,
                "timestamp": now,
            })
        except Exception:
            continue
    return {
        "success": len(data_list) > 0,
        "data": data_list,
        "source": "yfinance",
    }


def _fetch_sina(codes_sina: List[str]) -> Dict[str, Any]:
    """新浪接口兜底（易 403）。入参为新浪代码如 int_dji, rt_hkHSI。"""
    import requests
    url = f"http://hq.sinajs.cn/list={','.join(codes_sina)}"
    headers = {
        "Referer": "https://finance.sina.com.cn/money/globalindex/index.shtml",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        text = response.content.decode("gbk", errors="ignore")
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}
    if not text or not text.strip():
        return {"success": False, "data": [], "message": "新浪返回空"}
    sina_name = {"int_dji": "道琼斯", "int_nasdaq": "纳斯达克", "int_sp500": "标普500", "int_nikkei": "日经225", "rt_hkHSI": "恒生指数"}
    data_list = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hsi_codes = ["rt_hkHSI", "HSI", "rt_hk", "int_hs"]
    for code in codes_sina:
        try:
            try_codes = hsi_codes if any(h in code.lower() for h in ["hsi", "hs", "hk"]) else [code]
            match = None
            for tc in try_codes:
                m = re.search(rf'var hq_str_{re.escape(tc)}="([^"]+)";', text)
                if m:
                    match = m
                    break
            if not match:
                continue
            fields = [f.strip() for f in match.group(1).split(",")]
            is_hsi = code in hsi_codes or "hsi" in code.lower()
            if is_hsi and len(fields) >= 9:
                name = fields[1] or sina_name.get(code, code)
                price = float(fields[2]) if fields[2] else None
                change = float(fields[7]) if len(fields) > 7 and fields[7] else None
                cp = fields[8] if len(fields) > 8 else None
                change_pct = None
                if cp:
                    try:
                        change_pct = float(str(cp).replace("%", "").strip())
                    except ValueError:
                        if price and change and price != 0:
                            change_pct = change / price * 100
            elif len(fields) >= 6:
                name = fields[0] or sina_name.get(code, code)
                price = float(fields[1]) if fields[1] else None
                change = float(fields[2]) if fields[2] else None
                change_pct = float(fields[3]) if fields[3] else None
            else:
                continue
            yf_code = SINA_CODE_TO_YF.get(code, code)
            data_list.append({
                "code": yf_code,
                "name": name,
                "price": price,
                "change": change,
                "change_pct": round(change_pct, 4) if change_pct is not None else None,
                "timestamp": now,
            })
        except Exception:
            continue
    return {
        "success": len(data_list) > 0,
        "data": data_list,
        "source": "hq.sinajs.cn",
    }


def _merge_by_symbol(order: List[str], by_sym: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [by_sym[s] for s in order if s in by_sym]


def fetch_global_index_spot(
    index_codes: Optional[str] = None,
    api_base_url: str = "http://localhost:5000",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取全球主要指数最新快照（延迟因交易所/数据源而异，非交易所毫秒级实时）。
    数据源顺序由 data_sources.global_index.latest.priority 配置，默认 yfinance → FMP → 新浪。
    支持参数：int_dji / ^DJI 等，默认返回道琼斯、纳斯达克、标普500、日经225、恒生。
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    symbols = _normalize_codes(index_codes)
    cfg = _load_global_latest_config()
    priority: List[str] = list(cfg.get("priority") or ["yfinance", "fmp", "sina"])
    fmp_cfg = cfg.get("fmp") or {}
    fmp_enabled = bool(fmp_cfg.get("enabled", True))
    fmp_keys = _resolve_fmp_api_keys(fmp_cfg) if fmp_enabled else []

    by_symbol: Dict[str, Dict[str, Any]] = {}
    sources_used: List[str] = []
    notes: List[str] = []

    for src in priority:
        missing = [s for s in symbols if s not in by_symbol]
        if not missing:
            break
        if src == "fmp":
            if not fmp_keys:
                continue
            res = _fetch_fmp(missing, fmp_keys)
            for row in res.get("data") or []:
                c = row.get("code")
                if c in missing:
                    by_symbol[c] = row
            if res.get("message"):
                notes.append(res["message"])
            if res.get("success") and res.get("data"):
                sources_used.append("financialmodelingprep.com/stable/quote")
        elif src == "yfinance":
            res = _fetch_yfinance(missing)
            for row in res.get("data") or []:
                c = row.get("code")
                if c in missing:
                    by_symbol[c] = row
            if res.get("message"):
                notes.append(str(res["message"]))
            if res.get("success") and res.get("data"):
                sources_used.append("yfinance")
        elif src == "sina":
            codes_sina = [YF_TO_SINA[s] for s in missing if s in YF_TO_SINA]
            if not codes_sina:
                codes_sina = ["int_dji", "int_nasdaq", "int_sp500", "int_nikkei", "rt_hkHSI"]
            fallback = _fetch_sina(codes_sina)
            for row in fallback.get("data") or []:
                c = row.get("code")
                if c in missing:
                    by_symbol[c] = row
            if fallback.get("message"):
                notes.append(str(fallback["message"]))
            if fallback.get("success") and fallback.get("data"):
                sources_used.append("hq.sinajs.cn")

    data = _merge_by_symbol(symbols, by_symbol)
    if data:
        src_label = sources_used[0] if len(sources_used) == 1 else "mixed"
        out: Dict[str, Any] = {
            "success": True,
            "count": len(data),
            "data": data,
            "source": src_label,
            "timestamp": ts,
            "semantics": "latest_snapshot",
            "note": "全球指数为各数据源最新可见值（含延迟），非毫秒级实时行情。",
        }
        if len(sources_used) > 1:
            out["sources_used"] = sources_used
        return out

    msg = "全部数据源均失败"
    if notes:
        msg += ": " + " | ".join(notes[:5])
    msg += "。FMP 免费档约 250 次/天，请检查 data_sources.global_index.latest.fmp 与 FMP_API_KEY。"
    return {
        "success": False,
        "count": 0,
        "data": [],
        "source": "none",
        "message": msg,
        "timestamp": ts,
        "semantics": "latest_snapshot",
    }


def tool_fetch_global_index_spot(index_codes: Optional[str] = None) -> Dict[str, Any]:
    """OpenClaw 工具：获取全球主要指数最新快照。"""
    return fetch_global_index_spot(index_codes=index_codes)
