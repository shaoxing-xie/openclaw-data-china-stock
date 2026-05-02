"""Optional probe: coarse import-level health + on-demand snapshot write (P2-data-health)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from plugins.utils.source_health import append_source_event, write_snapshot as persist_snapshot_to_disk


def _parse_ids(raw: Optional[str]) -> List[str]:
    s = (raw or "").strip()
    if not s:
        return ["akshare", "sina", "yfinance", "eastmoney", "tushare"]
    return [x.strip() for x in s.split(",") if x.strip()]


def tool_probe_source_health(
    source_ids: Optional[str] = None,
    *,
    write_snapshot: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    """
    Coarse health rows (import-level smoke). Set ``write_snapshot=true`` to persist
    ``data/meta/source_health_snapshot.json`` and append one JSONL event.
    """
    ids = _parse_ids(source_ids)
    rows: List[Dict[str, Any]] = []
    for sid in ids:
        ok = True
        detail = "skipped_import_check"
        try:
            if sid == "akshare":
                import akshare as ak  # type: ignore

                detail = f"akshare_version={getattr(ak, '__version__', 'unknown')}"
            elif sid == "yfinance":
                import yfinance as yf  # type: ignore

                detail = f"yfinance_version={getattr(yf, '__version__', 'unknown')}"
            else:
                detail = "import_probe_not_configured_for_source"
        except Exception as e:
            ok = False
            detail = str(e)[:200]
        rows.append({"source_id": sid, "ok": ok, "detail": detail})

    rid = str(uuid.uuid4())
    if write_snapshot:
        path = persist_snapshot_to_disk(rows, run_id=rid)
        append_source_event(
            {
                "event": "source_health_probe",
                "run_id": rid,
                "source_ids": ids,
                "success": True,
            }
        )
        return {
            "success": True,
            "message": "snapshot_written",
            "run_id": rid,
            "path": str(path),
            "data": rows,
        }
    return {"success": True, "message": "dry_run", "run_id": rid, "data": rows}
