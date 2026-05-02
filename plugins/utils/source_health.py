"""Lightweight data-source health snapshot + JSONL events (P2-data-health)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def snapshot_path() -> Path:
    base = os.environ.get("OPENCLAW_DATA_DIR")
    if base:
        return Path(base) / "meta" / "source_health_snapshot.json"
    return _repo_root() / "data" / "meta" / "source_health_snapshot.json"


def events_path() -> Path:
    base = os.environ.get("OPENCLAW_DATA_DIR")
    if base:
        return Path(base) / "logs" / "source_events.jsonl"
    return _repo_root() / "data" / "logs" / "source_events.jsonl"


def append_source_event(record: Dict[str, Any]) -> None:
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_snapshot(rows: List[Dict[str, Any]], *, run_id: Optional[str] = None) -> Path:
    path = snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "schema_name": "source_health_snapshot",
            "schema_version": "0.1.0",
            "data_layer": "L3",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "quality_status": "ok",
        },
        "sources": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_snapshot() -> Optional[Dict[str, Any]]:
    path = snapshot_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
