from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import akshare as ak
except Exception:  # noqa: BLE001
    ak = None  # type: ignore[assignment]

from plugins.data_collection.a_share_fund_flow import tool_fetch_a_share_fund_flow
from plugins.data_collection.limit_up.sector_heat import tool_sector_heat_score
from plugins.data_collection.sector import tool_fetch_sector_data


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _normalize_score_0_100(value: Optional[float], lo: float, hi: float) -> float:
    if value is None:
        return 0.0
    if hi <= lo:
        return 0.0
    clipped = max(lo, min(hi, float(value)))
    return round((clipped - lo) / (hi - lo) * 100.0, 2)


def _as_date(date: Optional[str]) -> Tuple[str, str]:
    if date:
        raw = str(date).strip()
        if len(raw) == 8 and raw.isdigit():
            return raw, f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw.replace("-", ""), raw
    today = datetime.now().strftime("%Y%m%d")
    return today, f"{today[0:4]}-{today[4:6]}-{today[6:8]}"


def _index_sector_metrics(sector_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in sector_rows:
        name = str(row.get("sector_name") or row.get("name") or "").strip()
        if not name:
            continue
        out[name] = row
    return out


def _index_fund_flow_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        name = str(
            row.get("sector_name")
            or row.get("板块名称")
            or row.get("名称")
            or row.get("name")
            or ""
        ).strip()
        if not name:
            continue
        out[name] = row
    return out


def _fund_flow_score(flow_row: Dict[str, Any]) -> float:
    net_inflow = _safe_float(
        flow_row.get("net_inflow")
        or flow_row.get("主力净流入")
        or flow_row.get("今日主力净流入-净额")
        or flow_row.get("今日主力净流入净额")
    )
    if net_inflow is None:
        return 0.0
    # 东财/同花顺资金口径常见到亿元级以上，这里采用宽窗口做归一化。
    return _normalize_score_0_100(net_inflow, lo=-5e9, hi=8e9)


def _board_change_fallback(top_k: int, min_heat_score: float) -> List[Dict[str, Any]]:
    """
    盘中兜底：使用东财板块异动全量，避免涨停池在早盘样本不足导致热点空窗。
    """
    if ak is None:
        return []
    try:
        df = ak.stock_board_change_em()
    except Exception:
        return []
    if df is None or getattr(df, "empty", True):
        return []

    hotspots: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        name = str(row.get("板块名称") or "").strip()
        if not name:
            continue
        change_pct = _safe_float(row.get("涨跌幅"))
        net_inflow = _safe_float(row.get("主力净流入"))
        change_count = _safe_float(row.get("板块异动总次数"))
        price_score = _normalize_score_0_100(change_pct, lo=-5.0, hi=5.0)
        fund_score = _normalize_score_0_100(net_inflow, lo=-8e4, hi=8e4)
        activity_score = _normalize_score_0_100(change_count, lo=0, hi=500)
        heat_score = round(price_score * 0.45 + fund_score * 0.35 + activity_score * 0.2, 2)
        if heat_score < min_heat_score:
            continue
        hotspots.append(
            {
                "name": name,
                "rank": 0,
                "heat_score": heat_score,
                "phase": "盘中异动",
                "reasons": [
                    f"板块异动总次数 {int(change_count or 0)}",
                    f"涨跌幅 {round(change_pct or 0.0, 2)}%",
                ],
                "top_stocks": [str(row.get("板块异动最频繁个股及所属类型-股票名称") or "")],
                "heat_components": {
                    "limit_up_score": round(activity_score, 2),
                    "fund_flow_score": round(fund_score, 2),
                    "price_change_score": round(price_score, 2),
                },
                "lineage": {
                    "board_change_count": int(change_count or 0),
                },
            }
        )
    hotspots.sort(key=lambda x: x["heat_score"], reverse=True)
    hotspots = hotspots[:top_k]
    for idx, item in enumerate(hotspots, start=1):
        item["rank"] = idx
    return hotspots


def _price_score(sector_row: Dict[str, Any]) -> float:
    change_pct = _safe_float(sector_row.get("change_percent") or sector_row.get("涨跌幅") or sector_row.get("pct_change"))
    return _normalize_score_0_100(change_pct, lo=-5.0, hi=5.0)


def _limit_up_score(heat_row: Dict[str, Any]) -> float:
    count = _safe_float(heat_row.get("limit_up_count"))
    return _normalize_score_0_100(count, lo=0.0, hi=8.0)


def _reasons(
    *,
    sector_name: str,
    limit_up_count: int,
    fund_score: float,
    price_score: float,
    phase: str,
) -> List[str]:
    reasons: List[str] = []
    if limit_up_count > 0:
        reasons.append(f"涨停家数 {limit_up_count}，热度阶段 {phase}")
    if fund_score >= 60:
        reasons.append("板块主力资金偏强")
    elif fund_score <= 35:
        reasons.append("板块主力资金偏弱")
    if price_score >= 60:
        reasons.append("板块涨幅处于强势区间")
    elif price_score <= 35:
        reasons.append("板块涨幅偏弱，分化风险较高")
    if not reasons:
        reasons.append(f"{sector_name}热度由多因子综合给出")
    return reasons


def tool_hotspot_discovery(
    date: Optional[str] = None,
    top_k: int = 5,
    min_heat_score: float = 30.0,
) -> Dict[str, Any]:
    """
    聚合涨停、资金流、板块涨跌幅，输出当日热点 TOPN。
    """
    ymd, trade_date = _as_date(date)
    top_k = max(1, min(int(top_k), 20))
    min_heat_score = float(min_heat_score)

    heat_payload = tool_sector_heat_score(date=ymd)
    sector_payload = tool_fetch_sector_data(sector_type="industry", period="today")
    fund_payload = tool_fetch_a_share_fund_flow(
        query_kind="sector_rank",
        sector_type="industry",
        rank_window="immediate",
        limit=200,
    )

    heat_rows = list(heat_payload.get("sectors") or [])
    sector_rows = list(sector_payload.get("all_data") or [])
    fund_rows = list((fund_payload.get("data") or {}).get("records") or fund_payload.get("records") or [])

    sector_map = _index_sector_metrics(sector_rows)
    fund_map = _index_fund_flow_metrics(fund_rows)
    hotspots: List[Dict[str, Any]] = []

    for row in heat_rows:
        sector_name = str(row.get("name") or "").strip()
        if not sector_name:
            continue
        limit_score = _limit_up_score(row)
        fund_score = _fund_flow_score(fund_map.get(sector_name, {}))
        price_score = _price_score(sector_map.get(sector_name, {}))
        heat_score = round(limit_score * 0.4 + fund_score * 0.35 + price_score * 0.25, 2)
        if heat_score < min_heat_score:
            continue
        leaders = list(row.get("leaders") or [])
        phase = str(row.get("phase") or "未知")
        limit_up_count = int(_safe_float(row.get("limit_up_count")) or 0)
        hotspots.append(
            {
                "name": sector_name,
                "rank": 0,
                "heat_score": heat_score,
                "phase": phase,
                "reasons": _reasons(
                    sector_name=sector_name,
                    limit_up_count=limit_up_count,
                    fund_score=fund_score,
                    price_score=price_score,
                    phase=phase,
                ),
                "top_stocks": [str(x.get("name") or "") for x in leaders if str(x.get("name") or "").strip()][:3],
                "heat_components": {
                    "limit_up_score": round(limit_score, 2),
                    "fund_flow_score": round(fund_score, 2),
                    "price_change_score": round(price_score, 2),
                },
                "lineage": {
                    "sector_heat_score": round(_safe_float(row.get("score")) or 0.0, 2),
                    "limit_up_count": limit_up_count,
                },
            }
        )

    hotspots.sort(key=lambda x: x["heat_score"], reverse=True)
    hotspots = hotspots[:top_k]
    for idx, item in enumerate(hotspots, start=1):
        item["rank"] = idx

    used_board_change = False
    if not hotspots:
        board_hotspots = _board_change_fallback(top_k=top_k, min_heat_score=min_heat_score)
        if board_hotspots:
            hotspots = board_hotspots
            used_board_change = True

    reasons: List[str] = []
    if not heat_payload.get("success"):
        reasons.append("sector_heat_unavailable")
    if not sector_payload.get("success"):
        reasons.append("sector_snapshot_unavailable")
    if not fund_payload.get("success"):
        reasons.append("fund_flow_unavailable")
    if used_board_change:
        reasons.append("board_change_fallback")
    quality_status = "degraded" if reasons else "ok"

    return {
        "success": True,
        "trade_date": trade_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "_meta": {
            "schema_name": "hotspot_discovery_view_v1",
            "schema_version": "1.0.0",
            "task_id": "hotspot-discovery",
            "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "data_layer": "L4",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "trade_date": trade_date,
            "quality_status": quality_status,
            "source_tools": [
                "tool_sector_heat_score",
                "tool_fetch_sector_data",
                "tool_fetch_a_share_fund_flow",
            ],
            "lineage_refs": [],
        },
        "quality_status": quality_status,
        "degraded_reason": ",".join(reasons) if reasons else None,
        "hotspots": hotspots,
    }

