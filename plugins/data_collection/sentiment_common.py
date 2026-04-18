"""
Shared helpers for sentiment tools.

This module centralizes:
- unified response contract
- lightweight quality gate
- in-process TTL cache helpers
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from plugins.utils.cache import TTLCache

_CACHE = TTLCache(default_ttl=300)


def build_cache_key(namespace: str, payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return f"{namespace}:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


def cache_get(key: str) -> Optional[Any]:
    return _CACHE.get(key)


def cache_set(key: str, value: Any, ttl: int) -> None:
    _CACHE.set(key, value, ttl=max(1, int(ttl)))


def infer_ttl_seconds(data_type: str, is_trading_hours: bool = True) -> int:
    if data_type == "northbound":
        return 86400
    if not is_trading_hours:
        return 1800
    if data_type in ("limit_up", "sector", "fund_flow"):
        return 600
    return 300


def quality_gate_records(
    records: Iterable[Dict[str, Any]],
    *,
    min_records: int = 1,
    required_fields: Optional[List[str]] = None,
    max_null_ratio: float = 0.7,
) -> Dict[str, Any]:
    rows = list(records)
    out: Dict[str, Any] = {
        "ok": True,
        "record_count": len(rows),
        "missing_fields": [],
        "null_ratio": 0.0,
        "reason": "ok",
    }
    if len(rows) < max(0, min_records):
        out.update({"ok": False, "reason": "insufficient_records"})
        return out
    if not rows:
        return out

    required_fields = required_fields or []
    missing: List[str] = []
    for field in required_fields:
        if not any(field in r for r in rows):
            missing.append(field)
    out["missing_fields"] = missing
    if missing:
        out.update({"ok": False, "reason": "missing_fields"})
        return out

    total_cells = len(rows) * max(1, len(rows[0]))
    null_cells = 0
    for row in rows:
        for v in row.values():
            if v is None:
                null_cells += 1
    null_ratio = float(null_cells) / float(total_cells) if total_cells else 0.0
    out["null_ratio"] = round(null_ratio, 4)
    if null_ratio > max_null_ratio:
        out.update({"ok": False, "reason": "too_many_nulls"})
    return out


def normalize_contract(
    *,
    success: bool,
    payload: Dict[str, Any],
    source: str,
    attempts: Optional[List[Dict[str, Any]]] = None,
    fallback_route: Optional[List[str]] = None,
    used_fallback: bool = False,
    data_quality: str = "fresh",
    cache_hit: bool = False,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    out = dict(payload)
    out["success"] = bool(success)
    out["source"] = source
    out["used_fallback"] = bool(used_fallback)
    out["fallback_route"] = fallback_route or ([a.get("source") for a in (attempts or []) if a.get("source")])
    out["attempts"] = attempts or []
    out["as_of"] = out.get("as_of") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out["data_quality"] = data_quality
    out["cache_hit"] = cache_hit
    out["error_code"] = error_code
    out["error_message"] = error_message
    if "explanation" not in out:
        out["explanation"] = ""
    return out
