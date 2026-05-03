"""
L2 entity tools: normalize symbols and delegate index constituents to reference_p1.

ETF 持仓：AkShare ``fund_portfolio_hold_em``（年报/季报维度，按自然年参数）。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from plugins.analysis.equity_factor_screening import _norm_code_6
from plugins.data_collection.stock.reference_p1 import _norm_index_code, tool_fetch_index_constituents

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MASTER_ENTITIES = _REPO_ROOT / "data" / "master_meta" / "entities.json"


def _load_master_entities() -> Dict[str, Any]:
    if not _MASTER_ENTITIES.is_file():
        return {}
    try:
        raw = json.loads(_MASTER_ENTITIES.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _guess_entity_type(code6: str) -> str:
    s = (code6 or "").strip()
    if not s or len(s) != 6 or not s.isdigit():
        return "unknown"
    if s.startswith(("51", "56", "58")):
        return "etf"
    if s.startswith(("15", "16", "18")):
        return "etf"
    if s.startswith(("000", "399")):
        return "index"
    if s.startswith(("60", "68")):
        return "stock"
    if s.startswith(("00", "30")):
        return "stock"
    if s.startswith("43") or s.startswith("83") or s.startswith("87"):
        return "stock"
    return "stock"


def _entity_id_stub(entity_type: str, code6: str) -> str:
    et = entity_type.lower()
    if et == "index":
        return f"idx:{code6}"
    if et == "etf":
        return f"etf:{code6}"
    if et == "stock":
        return f"stk:{code6}"
    return f"unk:{code6}"


def tool_resolve_symbol(symbol: str, **_: Any) -> Dict[str, Any]:
    """
    Resolve a user symbol to canonical 6-digit code, guessed type, and optional entity_id stub.

    Does not call upstream; pure normalization + heuristics.
    """
    raw = (symbol or "").strip()
    if not raw:
        return {
            "success": False,
            "message": "empty symbol",
            "quality_status": "error",
            "_meta": {
                "schema_name": "entity_resolve_v1",
                "schema_version": "1.0.0",
                "data_layer": "L2_entity",
                "generated_at": datetime.now().isoformat(),
            },
            "data": {},
        }

    idx_try = _norm_index_code(raw)
    if raw.isdigit() and len(raw) > 6 and idx_try:
        code6 = idx_try
        entity_type = "index"
    else:
        code6 = _norm_code_6(raw)
        entity_type = _guess_entity_type(code6)

    conf = 0.55 if entity_type == "unknown" else 0.85
    if entity_type == "index" and raw != code6:
        conf = min(0.95, conf + 0.05)

    return {
        "success": True,
        "message": "resolve ok",
        "quality_status": "ok",
        "_meta": {
            "schema_name": "entity_resolve_v1",
            "schema_version": "1.0.0",
            "data_layer": "L2_entity",
            "generated_at": datetime.now().isoformat(),
            "lineage_refs": ["_norm_code_6", "_norm_index_code"],
        },
        "data": {
            "input": raw,
            "canonical_code": code6,
            "entity_type": entity_type,
            "entity_id": _entity_id_stub(entity_type, code6),
            "confidence": conf,
        },
    }


def tool_batch_resolve_symbol(symbols: str, **_: Any) -> Dict[str, Any]:
    """Comma-separated symbols -> list of resolve payloads."""
    parts = [p.strip() for p in str(symbols or "").split(",") if p.strip()]
    rows: List[Dict[str, Any]] = []
    for p in parts[:200]:
        r = tool_resolve_symbol(p)
        rows.append((r.get("data") or {}) | {"_raw": p, "success": r.get("success"), "quality_status": r.get("quality_status")})
    return {
        "success": True,
        "message": "batch_resolve ok",
        "quality_status": "ok",
        "_meta": {
            "schema_name": "entity_batch_resolve_v1",
            "schema_version": "1.0.0",
            "data_layer": "L2_entity",
            "generated_at": datetime.now().isoformat(),
        },
        "data": {"items": rows, "count": len(rows)},
    }


def tool_get_entity_meta(symbol: str, **_: Any) -> Dict[str, Any]:
    """
    Entity card: resolve + optional static ``data/master_meta/entities.json`` overlay.
    """
    r = tool_resolve_symbol(symbol)
    if not r.get("success"):
        return r
    d = r.get("data") or {}
    code6 = str(d.get("canonical_code") or "")
    et = str(d.get("entity_type") or "unknown")
    master = _load_master_entities()
    ent_map = master.get("entities") if isinstance(master.get("entities"), dict) else {}
    row = ent_map.get(code6) if isinstance(ent_map, dict) else None
    name = None
    extra: Dict[str, Any] = {}
    if isinstance(row, dict):
        name = row.get("name")
        for k in ("list_board", "exchange_hint", "tracking_index"):
            if row.get(k) is not None:
                extra[k] = row.get(k)
    q = "ok" if name else "degraded"
    note = (
        "master_meta 命中静态卡片"
        if name
        else "未在 data/master_meta/entities.json 命中名称；可扩展该文件或后续接上游"
    )
    lineage = ["tool_resolve_symbol", "data/master_meta/entities.json"]
    return {
        "success": True,
        "message": "entity_meta ok",
        "quality_status": q,
        "_meta": {
            "schema_name": "entity_meta_v1",
            "schema_version": "1.0.0",
            "data_layer": "L2_entity",
            "generated_at": datetime.now().isoformat(),
            "lineage_refs": lineage,
        },
        "data": {
            "entity_id": d.get("entity_id"),
            "canonical_code": code6,
            "entity_type": et,
            "name": name,
            "master_meta_schema_version": master.get("schema_version"),
            **extra,
            "note": note,
        },
    }


def tool_get_index_constituents(
    index_code: str,
    include_weight: bool = False,
    provider_preference: str = "auto",
    max_rows: int = 0,
    **_: Any,
) -> Dict[str, Any]:
    """Delegate to reference_p1.tool_fetch_index_constituents (single registration)."""
    return tool_fetch_index_constituents(
        index_code=index_code,
        include_weight=include_weight,
        provider_preference=provider_preference,
        max_rows=max_rows,
    )


def _fetch_etf_holdings_via_em(code6: str, max_rows: int) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    try:
        import akshare as ak  # type: ignore
    except Exception as e:  # noqa: BLE001
        return [], None, str(e)
    year = datetime.now().year
    last_err: Optional[str] = None
    for y in (year, year - 1, year - 2):
        try:
            df = ak.fund_portfolio_hold_em(symbol=code6, date=str(y))
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            continue
        if df is None or getattr(df, "empty", True):
            last_err = last_err or f"empty portfolio year={y}"
            continue
        n = max(1, min(int(max_rows or 50), 500))
        items: List[Dict[str, Any]] = []
        head = df.head(n)
        for _, row in head.iterrows():
            sc = str(row.get("股票代码") or "").strip()
            sc = sc.zfill(6)[:6] if sc.isdigit() else sc
            items.append(
                {
                    "stock_code": sc,
                    "name": str(row.get("股票名称") or "").strip(),
                    "weight_pct": float(row.get("占净值比例") or 0) if row.get("占净值比例") is not None else None,
                    "quarter": str(row.get("季度") or "")[:64],
                }
            )
        return items, str(y), None
    return [], None, last_err or "fund_portfolio_hold_em failed"


def tool_get_etf_holdings(
    etf_code: str,
    max_rows: int = 50,
    **_: Any,
) -> Dict[str, Any]:
    """
    ETF 前十大重仓（按东方财富基金持仓披露；自然年 ``date`` 回退）。
    """
    code6 = _norm_code_6(etf_code)
    et_guess = _guess_entity_type(code6)
    if et_guess != "etf":
        return {
            "success": False,
            "message": f"code {code6} does not look like an ETF code",
            "quality_status": "degraded",
            "_meta": {
                "schema_name": "entity_etf_holdings_v1",
                "schema_version": "1.0.0",
                "data_layer": "L2_entity",
                "generated_at": datetime.now().isoformat(),
                "lineage_refs": [],
            },
            "data": {"etf_code": code6, "items": [], "count": 0},
        }
    items, asof_year, err = _fetch_etf_holdings_via_em(code6, max_rows)
    ok = bool(items)
    return {
        "success": ok,
        "message": "etf_holdings ok" if ok else (err or "etf_holdings failed"),
        "quality_status": "ok" if ok else "degraded",
        "_meta": {
            "schema_name": "entity_etf_holdings_v1",
            "schema_version": "1.0.0",
            "data_layer": "L2_entity",
            "generated_at": datetime.now().isoformat(),
            "lineage_refs": ["akshare.fund_portfolio_hold_em"],
        },
        "data": {
            "etf_code": code6,
            "portfolio_year": asof_year,
            "items": items,
            "count": len(items),
            "note": None if ok else (err or "upstream error"),
        },
    }
