from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from plugins.data_collection.sentiment_common import normalize_contract, quality_gate_records


def _now_trade_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _meta(task_id: str, trade_date: str, quality_status: str, source_tools: List[str], lineage_refs: List[str]) -> Dict[str, Any]:
    return {
        "schema_name": "raw_ths_sector_constituents_v1",
        "schema_version": "1.0.0",
        "task_id": task_id,
        "run_id": datetime.now().strftime("%Y%m%dT%H%M%S"),
        "data_layer": "L1",
        "generated_at": datetime.now().isoformat(),
        "trade_date": trade_date,
        "source_tools": source_tools,
        "lineage_refs": lineage_refs,
        "quality_status": quality_status,
    }


def tool_fetch_sector_constituents(
    sector_code: str,
    sector_type: str = "industry",
    trade_date: str | None = None,
) -> Dict[str, Any]:
    """
    获取行业/概念板块成分股。

    说明：
    - 主链路尝试东方财富行业/概念成分接口（akshare *_cons_em）
    - 若失败，降级为指数成分近似（当 sector_code 为 6 位指数代码）
    """
    td = (trade_date or _now_trade_date()).strip()
    sc = str(sector_code or "").strip()
    st = str(sector_type or "industry").strip().lower()
    attempts: List[Dict[str, Any]] = []
    source_tools: List[str] = []

    if not sc:
        return normalize_contract(
            success=False,
            payload={
                "error": "sector_code is required",
                "data": {"sector_code": sc, "sector_type": st, "trade_date": td, "constituents": []},
                "_meta": _meta("etf-rotation-research", td, "error", [], []),
                "quality_status": "error",
            },
            source="sector_constituents",
            attempts=attempts,
            used_fallback=False,
            data_quality="partial",
            error_code="VALIDATION_ERROR",
            error_message="sector_code is required",
            quality_data_type="sector",
        )

    # 主链路：akshare em 成分
    try:
        import akshare as ak  # type: ignore

        if st == "industry":
            df = ak.stock_board_industry_cons_em(symbol=sc)
        elif st == "concept":
            df = ak.stock_board_concept_cons_em(symbol=sc)
        else:
            raise ValueError("sector_type must be industry/concept")
        attempts.append({"source": f"akshare.{st}_cons_em", "ok": True, "message": "ok"})
        source_tools.append("akshare.stock_board_*_cons_em")
        items: List[Dict[str, Any]] = []
        if df is not None and not df.empty:
            # 常见字段：代码/名称/最新价/涨跌幅/成交额/市盈率等
            code_col = "代码" if "代码" in df.columns else ("股票代码" if "股票代码" in df.columns else df.columns[0])
            name_col = "名称" if "名称" in df.columns else ("股票名称" if "股票名称" in df.columns else None)
            for _, row in df.iterrows():
                sym = str(row.get(code_col, "")).strip()
                if not sym:
                    continue
                nm = str(row.get(name_col, "")).strip() if name_col else ""
                items.append({"symbol": sym, "name": nm, "weight": None})
        gate = quality_gate_records(items, min_records=1, required_fields=["symbol"])
        q = "ok" if gate.get("ok") else "degraded"
        payload = {
            "data": {
                "sector_code": sc,
                "sector_type": st,
                "trade_date": td,
                "total_count": len(items),
                "constituents": items,
            },
            "_meta": _meta("etf-rotation-research", td, q, source_tools, [f"akshare:{st}_cons_em"]),
            "quality_status": q,
        }
        return normalize_contract(
            success=True,
            payload=payload,
            source=f"akshare.{st}_cons_em",
            attempts=attempts,
            used_fallback=False,
            data_quality="fresh" if q == "ok" else "partial",
            quality_data_type="sector",
        )
    except Exception as e:  # noqa: BLE001
        attempts.append({"source": f"akshare.{st}_cons_em", "ok": False, "message": str(e)[:220]})

    # 降级：指数成分近似（若传入的是指数代码）
    try:
        from plugins.data_collection.stock.reference_p1 import tool_fetch_index_constituents

        if sc.isdigit() and len(sc) >= 6:
            r = tool_fetch_index_constituents(index_code=sc[:6], include_weight=True)
            if r.get("success"):
                rows = r.get("data") or []
                items = []
                for it in rows:
                    items.append(
                        {
                            "symbol": str(it.get("成分券代码") or it.get("code") or "").strip(),
                            "name": str(it.get("成分券名称") or it.get("name") or "").strip(),
                            "weight": it.get("权重"),
                        }
                    )
                items = [x for x in items if x["symbol"]]
                source_tools.append("tool_fetch_index_constituents")
                payload = {
                    "data": {
                        "sector_code": sc,
                        "sector_type": st,
                        "trade_date": td,
                        "total_count": len(items),
                        "constituents": items,
                        "proxy_mode": True,
                        "proxy_reason": "sector_constituents_unavailable_use_index_constituents",
                    },
                    "_meta": _meta(
                        "etf-rotation-research",
                        td,
                        "degraded",
                        source_tools,
                        ["tool_fetch_index_constituents"],
                    ),
                    "quality_status": "degraded",
                }
                attempts.append({"source": "tool_fetch_index_constituents", "ok": True, "message": "proxy_ok"})
                return normalize_contract(
                    success=True,
                    payload=payload,
                    source="index_constituents_proxy",
                    attempts=attempts,
                    used_fallback=True,
                    data_quality="partial",
                    quality_data_type="sector",
                )
    except Exception as e:  # noqa: BLE001
        attempts.append({"source": "tool_fetch_index_constituents", "ok": False, "message": str(e)[:220]})

    return normalize_contract(
        success=False,
        payload={
            "error": "sector constituents unavailable",
            "data": {"sector_code": sc, "sector_type": st, "trade_date": td, "constituents": []},
            "_meta": _meta("etf-rotation-research", td, "error", source_tools, []),
            "quality_status": "error",
        },
        source="sector_constituents",
        attempts=attempts,
        used_fallback=False,
        data_quality="partial",
        error_code="UPSTREAM_FETCH_FAILED",
        error_message="sector constituents unavailable",
        quality_data_type="sector",
    )

