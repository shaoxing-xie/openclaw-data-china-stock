"""Lightweight data-source health snapshot + JSONL events (P2-data-health)."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROBE_HISTORY_MAX_BYTES = 2 * 1024 * 1024


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


def probe_history_jsonl_path() -> Path:
    base = os.environ.get("OPENCLAW_DATA_DIR")
    if base:
        return Path(base) / "logs" / "source_health_probe_history.jsonl"
    return _repo_root() / "data" / "logs" / "source_health_probe_history.jsonl"


def rollup_path() -> Path:
    return snapshot_path().parent / "source_health_history_rollup.json"


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


def _trim_jsonl_by_size(path: Path, max_bytes: int) -> None:
    try:
        sz = path.stat().st_size
    except OSError:
        return
    if sz <= max_bytes:
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return
    drop = max(1, len(lines) // 4)
    path.write_text("\n".join(lines[drop:]) + "\n", encoding="utf-8")


def append_probe_history_sample(rows: List[Dict[str, Any]], run_id: str) -> None:
    """Append one probe sample (per-source ok flags) and refresh 7-day rollup JSON."""
    path = probe_history_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sources_ok = {str(r.get("source_id")): bool(r.get("ok")) for r in rows if r.get("source_id")}
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "trade_date": day,
        "sources_ok": sources_ok,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    _trim_jsonl_by_size(path, PROBE_HISTORY_MAX_BYTES)
    write_probe_history_rollup(days=7)


def write_probe_history_rollup(days: int = 7) -> Path:
    """Aggregate probe history JSONL for Chart Console trend chart."""
    path_in = probe_history_jsonl_path()
    path_out = rollup_path()
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=max(0, int(days) - 1))

    cell: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "n": 0}))
    if path_in.is_file():
        for line in path_in.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            d_raw = rec.get("trade_date")
            if not d_raw:
                continue
            try:
                d_part = str(d_raw)[:10]
                dd = datetime.strptime(d_part, "%Y-%m-%d").date()
            except Exception:
                continue
            if dd < cutoff:
                continue
            for sid, ok in (rec.get("sources_ok") or {}).items():
                sid = str(sid)
                cell[sid][d_part]["n"] += 1
                if ok:
                    cell[sid][d_part]["ok"] += 1

    series: Dict[str, List[Dict[str, Any]]] = {}
    for sid, dates_map in cell.items():
        arr: List[Dict[str, Any]] = []
        for d in sorted(dates_map.keys()):
            n = dates_map[d]["n"]
            okc = dates_map[d]["ok"]
            arr.append(
                {
                    "date": d,
                    "success_rate": (float(okc) / float(n)) if n else 0.0,
                    "samples": int(n),
                }
            )
        series[sid] = arr

    payload = {
        "_meta": {
            "schema_name": "source_health_history_rollup",
            "schema_version": "1.0.0",
            "data_layer": "L4",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "quality_status": "ok",
            "days": int(days),
        },
        "series": series,
    }
    path_out.parent.mkdir(parents=True, exist_ok=True)
    path_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path_out
