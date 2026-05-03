"""
Aggregate ``attempts`` lists (list of dicts with source_id / stage) for observability.
Read-only; no I/O.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


def summarize_attempts(attempts: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    rows = attempts if isinstance(attempts, list) else []
    by_source: Counter[str] = Counter()
    by_stage: Counter[str] = Counter()
    for a in rows:
        if not isinstance(a, dict):
            continue
        sid = str(a.get("source_id") or a.get("source") or "unknown")
        by_source[sid] += 1
        st = str(a.get("source_stage") or a.get("stage") or "")
        if st:
            by_stage[st] += 1
    return {
        "total_events": len(rows),
        "by_source_id": dict(by_source),
        "by_stage": dict(by_stage),
    }


def rollup_from_tool_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    att = payload.get("attempts") if isinstance(payload, dict) else None
    return summarize_attempts(att if isinstance(att, list) else [])


def tool_summarize_attempts(attempts_json: str = "[]", dataset_id: str = "", **_: Any) -> Dict[str, Any]:
    """
    Tool entry: summarize a serialized ``attempts`` JSON array (e.g. copied from another tool output).
    """
    import json
    from datetime import datetime

    try:
        raw = json.loads(attempts_json or "[]")
    except Exception:
        raw = []
    if not isinstance(raw, list):
        raw = []
    rows = [x for x in raw if isinstance(x, dict)]
    summary = summarize_attempts(rows)
    did = (dataset_id or "").strip()
    if did:
        summary = {**summary, "dataset_id": did}
    return {
        "success": True,
        "message": "attempts summary ok",
        "quality_status": "ok",
        "_meta": {
            "schema_name": "attempts_summary_v1",
            "schema_version": "1.0.0",
            "data_layer": "L2_entity",
            "generated_at": datetime.now().isoformat(),
        },
        "data": summary,
    }
