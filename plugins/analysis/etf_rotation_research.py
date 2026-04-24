from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from plugins.analysis.etf_share import tool_calculate_share_trend
from plugins.analysis.sector_breadth import tool_calculate_sector_breadth
from plugins.analysis.sector_leadership import tool_calculate_sector_leadership
from plugins.analysis.sector_momentum_v2 import tool_calculate_sector_momentum_v2


def tool_etf_rotation_research(
    etf_pool: str = "510300,510500,159915",
    lookback_days: int = 120,
    top_k: int = 5,
    trade_date: str | None = None,
    **_: Any,
) -> Dict[str, Any]:
    """
    轻量轮动研究入口（用于修复 TOOL_MAP 映射与提供统一契约）。
    """
    td = (trade_date or datetime.now().strftime("%Y-%m-%d")).strip()
    symbols: List[str] = [s.strip() for s in str(etf_pool).split(",") if s.strip()]
    symbol_scores: List[Dict[str, Any]] = []
    attempts: List[Dict[str, Any]] = []

    for symbol in symbols:
        share = tool_calculate_share_trend(etf_code=symbol, windows=[5, 20, 60], trade_date=td)
        trend_data = (share.get("data") or {}) if isinstance(share, dict) else {}
        trend_score = float(trend_data.get("trend_score") or 0.0)
        quality = str(share.get("quality_status") or "degraded") if isinstance(share, dict) else "degraded"
        symbol_scores.append(
            {
                "symbol": symbol,
                "score": trend_score,
                "score_breakdown": {"share_trend": trend_score},
                "quality_status": quality,
            }
        )
        attempts.extend((share.get("attempts") or []) if isinstance(share, dict) else [])

    # 板块维度（代理）
    breadth = tool_calculate_sector_breadth(sector_code="半导体", lookback_days=20, trade_date=td)
    leadership = tool_calculate_sector_leadership(sector_code="半导体", lookback_days=60, top_k=5, trade_date=td)
    momentum = tool_calculate_sector_momentum_v2(sector_code="半导体", lookback_days=20, trade_date=td)
    attempts.extend((breadth.get("attempts") or []) if isinstance(breadth, dict) else [])
    attempts.extend((leadership.get("attempts") or []) if isinstance(leadership, dict) else [])
    attempts.extend((momentum.get("attempts") or []) if isinstance(momentum, dict) else [])

    ranked = sorted(symbol_scores, key=lambda x: x["score"], reverse=True)
    ranked = ranked[: max(1, int(top_k))]
    quality_status = "ok"
    if any(str(x.get("quality_status")) != "ok" for x in ranked):
        quality_status = "degraded"

    return {
        "success": True,
        "message": "etf_rotation_research ok",
        "quality_status": quality_status,
        "_meta": {
            "schema_name": "decision_rotation_candidates_v1",
            "schema_version": "1.0.0",
            "task_id": "etf-rotation-research",
            "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "data_layer": "L3",
            "generated_at": datetime.now().isoformat(),
            "trade_date": td,
            "source_tools": [
                "tool_calculate_share_trend",
                "tool_calculate_sector_breadth",
                "tool_calculate_sector_leadership",
                "tool_calculate_sector_momentum_v2",
            ],
            "lineage_refs": [],
            "quality_status": quality_status,
        },
        "data": {
            "trade_date": td,
            "lookback_days": lookback_days,
            "ranked": ranked,
            "top5": ranked[:5],
            "context": {
                "breadth": breadth.get("data") if isinstance(breadth, dict) else {},
                "leadership": leadership.get("data") if isinstance(leadership, dict) else {},
                "momentum_v2": momentum.get("data") if isinstance(momentum, dict) else {},
            },
        },
        "attempts": attempts,
    }

