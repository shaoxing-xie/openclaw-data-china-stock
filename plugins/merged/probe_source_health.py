"""Optional probe: coarse import-level health + on-demand snapshot write (P2-data-health)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from plugins.utils.error_codes import ErrorCode, QualityStatus
from plugins.utils.source_health import (
    append_probe_history_sample,
    append_source_event,
    write_snapshot as persist_snapshot_to_disk,
)


def _parse_ids(raw: Optional[str]) -> List[str]:
    s = (raw or "").strip()
    if not s:
        return ["akshare", "sina", "yfinance", "eastmoney", "tushare"]
    return [x.strip() for x in s.split(",") if x.strip()]


def tool_probe_source_health(
    source_ids: Optional[str] = None,
    *,
    write_snapshot: bool = False,
    include_catalog_digest: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    """
    Coarse health rows (import-level smoke). Set ``write_snapshot=true`` to persist
    ``data/meta/source_health_snapshot.json`` and append one JSONL event.

    ``include_catalog_digest``: attach read-only ``factor_registry`` / ``source_chains`` summary (no network).
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
        row: Dict[str, Any] = {"source_id": sid, "ok": ok, "detail": detail}
        if not ok:
            row["error_code"] = ErrorCode.PLUGIN_UNAVAILABLE
        rows.append(row)

    rid = str(uuid.uuid4())
    if write_snapshot:
        try:
            path = persist_snapshot_to_disk(rows, run_id=rid)
            append_source_event(
                {
                    "event": "source_health_probe",
                    "run_id": rid,
                    "source_ids": ids,
                    "success": True,
                }
            )
            append_probe_history_sample(rows, rid)
        except Exception as e:
            return {
                "success": False,
                "message": f"snapshot_write_failed: {e}",
                "error_code": ErrorCode.UPSTREAM_FETCH_FAILED,
                "run_id": rid,
                "data": rows,
                "_meta": {
                    "schema_name": "tool_probe_source_health",
                    "schema_version": "1",
                    "quality_status": QualityStatus.ERROR,
                    "error_code": ErrorCode.UPSTREAM_FETCH_FAILED,
                },
            }
        out: Dict[str, Any] = {
            "success": True,
            "message": "snapshot_written",
            "run_id": rid,
            "path": str(path),
            "data": rows,
        }
        if include_catalog_digest:
            try:
                from plugins.utils.catalog_digest_tool import tool_plugin_catalog_digest

                out["catalog_digest"] = tool_plugin_catalog_digest().get("data")
            except Exception as e:
                out["catalog_digest_error"] = str(e)[:200]
        return out
    out_dry: Dict[str, Any] = {"success": True, "message": "dry_run", "run_id": rid, "data": rows}
    if include_catalog_digest:
        try:
            from plugins.utils.catalog_digest_tool import tool_plugin_catalog_digest

            out_dry["catalog_digest"] = tool_plugin_catalog_digest().get("data")
        except Exception as e:
            out_dry["catalog_digest_error"] = str(e)[:200]
    return out_dry
