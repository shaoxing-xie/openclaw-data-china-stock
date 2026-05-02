from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class RpsPoint:
    code: str
    ret: float
    rank: int
    rps: float


def _parse_trade_date(trade_date: str) -> str:
    s = (trade_date or "").strip()
    if not s:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        pass
    try:
        dt = datetime.strptime(s, "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _window_start(trade_date: str, lookback_days: int) -> str:
    td = datetime.strptime(trade_date, "%Y-%m-%d")
    # Use calendar days as a simple bound; upstream cache typically has enough bars.
    start = td - timedelta(days=max(int(lookback_days) * 2, 10))
    return start.strftime("%Y-%m-%d")


def _extract_klines(obj: Any) -> List[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return []
    data = obj.get("data")
    if isinstance(data, list):
        # multi-etf: [{...klines...}, ...]
        return []
    if not isinstance(data, dict):
        return []
    kl = data.get("klines")
    if isinstance(kl, list):
        return [x for x in kl if isinstance(x, dict)]
    return []


def _calc_return_from_klines(klines: List[Dict[str, Any]], *, lookback_days: int) -> Optional[float]:
    if not klines:
        return None
    # Assume klines are chronological; if not, sort by date.
    def _kdate(k: Dict[str, Any]) -> str:
        return str(k.get("date") or "")

    if len(klines) >= 2 and _kdate(klines[0]) > _kdate(klines[-1]):
        klines = sorted(klines, key=_kdate)
    # Find a slice of last lookback_days bars.
    bars = klines[-int(lookback_days) :] if len(klines) >= int(lookback_days) else klines
    if len(bars) < 2:
        return None
    try:
        c0 = float(bars[0].get("close") or 0.0)
        c1 = float(bars[-1].get("close") or 0.0)
    except Exception:
        return None
    if c0 <= 0 or c1 <= 0:
        return None
    return (c1 - c0) / c0


def _rps_from_returns(pairs: List[Tuple[str, float]]) -> List[RpsPoint]:
    pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
    n = len(pairs_sorted)
    out: List[RpsPoint] = []
    for i, (code, ret) in enumerate(pairs_sorted):
        if n <= 1:
            rps = 100.0
        else:
            rps = (1.0 - (i / (n - 1))) * 100.0
        out.append(RpsPoint(code=code, ret=ret, rank=i + 1, rps=float(rps)))
    return out


def calculate_rps_for_etfs(
    *,
    etf_codes: Iterable[str],
    lookback_days: int,
    trade_date: str = "",
    mode: str = "production",
) -> Dict[str, Any]:
    """
    Compute RPS across a set of ETFs using N-day return.

    Notes:
    - Uses ETF historical tool output (close series) as the single data source.
    - This is intentionally minimal (Phase A). Phase B may switch to index series if available.
    """
    td = _parse_trade_date(trade_date)
    codes = [str(x).strip() for x in etf_codes if str(x).strip()]
    codes = list(dict.fromkeys(codes))  # stable unique
    if not codes:
        return {"success": False, "message": "etf_codes 为空", "data": None, "quality_status": "error"}
    lb = max(2, int(lookback_days or 0))

    from plugins.merged.fetch_market_data import tool_fetch_market_data

    returns: List[Tuple[str, float]] = []
    missing: List[str] = []
    attempts: List[Dict[str, Any]] = []

    start_date = _window_start(td, lb)
    end_date = td
    for code in codes:
        try:
            resp = tool_fetch_market_data(
                asset_type="etf",
                view="historical",
                asset_code=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                lookback_days=lb,
                mode=mode,
            )
            ok = bool(isinstance(resp, dict) and resp.get("success"))
            attempts.append({"etf_code": code, "ok": ok, "source": (resp or {}).get("source")})
            if not ok:
                missing.append(code)
                continue
            klines = _extract_klines(resp)
            ret = _calc_return_from_klines(klines, lookback_days=lb)
            if ret is None:
                missing.append(code)
                continue
            returns.append((code, float(ret)))
        except Exception as e:  # noqa: BLE001
            attempts.append({"etf_code": code, "ok": False, "error": str(e)[:160]})
            missing.append(code)

    if len(returns) < max(3, int(len(codes) * 0.5)):
        return {
            "success": False,
            "message": "有效ETF数据不足，无法计算RPS",
            "quality_status": "error",
            "data": {
                "trade_date": td,
                "lookback_days": lb,
                "requested": len(codes),
                "available": len(returns),
                "missing": missing[:50],
                "attempts": attempts,
            },
        }

    points = _rps_from_returns(returns)
    rps_map = {p.code: {"rps": p.rps, "rank": p.rank, "return": p.ret} for p in points}
    return {
        "success": True,
        "message": "rps ok",
        "quality_status": "ok" if len(missing) <= max(1, int(len(codes) * 0.1)) else "degraded",
        "data": {
            "trade_date": td,
            "lookback_days": lb,
            "count": len(points),
            "rps": rps_map,
            "missing": missing,
            "attempts": attempts,
        },
    }


def tool_calculate_sector_rps(
    *,
    lookback_days: List[int] | int = 20,
    etf_codes: str = "",
    trade_date: str = "",
    mode: str = "production",
) -> Dict[str, Any]:
    """
    Tool: calculate RPS across sector ETF universe.

    - If etf_codes is empty, uses configured sector ETF mapping.
    - lookback_days can be an int or list of ints.
    """
    from plugins.analysis.sector_etf_mapping import get_etf_codes_from_mapping

    td = _parse_trade_date(trade_date)
    if isinstance(lookback_days, int):
        lbs = [lookback_days]
    else:
        lbs = [int(x) for x in (lookback_days or []) if int(x) > 0]
    if not lbs:
        lbs = [20]
    lbs = sorted(set(lbs))

    codes: List[str] = [s.strip() for s in str(etf_codes or "").split(",") if s.strip()]
    if not codes:
        mapping_info = get_etf_codes_from_mapping(min_coverage=1)
        codes = list(mapping_info.get("etf_codes") or [])

    windows: Dict[str, Any] = {}
    quality = "ok"
    for lb in lbs:
        out = calculate_rps_for_etfs(etf_codes=codes, lookback_days=lb, trade_date=td, mode=mode)
        if not out.get("success"):
            quality = "degraded" if quality == "ok" else quality
        wq = out.get("quality_status") or "degraded"
        if wq != "ok":
            quality = "degraded" if quality != "error" else quality
        windows[str(lb)] = out.get("data")

    return {
        "success": True,
        "message": "sector rps calculated",
        "quality_status": quality,
        "data": {"trade_date": td, "lookback_days": lbs, "windows": windows, "etf_codes": codes},
    }

