#!/usr/bin/env python3
import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins.data_collection.futures.fetch_a50 import tool_fetch_a50_data
from plugins.data_collection.index.fetch_global import tool_fetch_global_index_spot


def _single_run() -> Dict[str, Any]:
    started = time.perf_counter()
    global_res = tool_fetch_global_index_spot(index_codes="^DJI,^IXIC,^GSPC")
    a50_first = tool_fetch_a50_data(data_type="spot", use_cache=True)
    a50_second = tool_fetch_a50_data(data_type="spot", use_cache=True)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "timestamp": datetime.now().isoformat(),
        "elapsed_ms": elapsed_ms,
        "global": {
            "success": bool(global_res.get("success")),
            "quality": global_res.get("quality"),
            "elapsed_ms": global_res.get("elapsed_ms"),
            "empty_value_ratio": _empty_ratio(global_res.get("data") or []),
        },
        "a50": {
            "first_success": bool(a50_first.get("success")),
            "second_success": bool(a50_second.get("success")),
            "cache_hit_second": bool(a50_second.get("cache_hit")),
            "cache_age_ms": a50_second.get("cache_age_ms"),
            "quality_second": a50_second.get("quality"),
            "elapsed_ms_second": a50_second.get("elapsed_ms"),
        },
    }


def _empty_ratio(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 1.0
    total = 0
    empty = 0
    for row in rows:
        for field in ("price", "change", "change_pct"):
            total += 1
            if row.get(field) is None:
                empty += 1
    return round(empty / total, 4) if total else 0.0


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _compare(before_path: str, after_path: str) -> Dict[str, Any]:
    before = json.loads(Path(before_path).read_text(encoding="utf-8"))
    after = json.loads(Path(after_path).read_text(encoding="utf-8"))
    return {
        "before_elapsed_ms": before.get("elapsed_ms"),
        "after_elapsed_ms": after.get("elapsed_ms"),
        "elapsed_delta_ms": (after.get("elapsed_ms") or 0) - (before.get("elapsed_ms") or 0),
        "before_empty_ratio": before.get("global", {}).get("empty_value_ratio"),
        "after_empty_ratio": after.get("global", {}).get("empty_value_ratio"),
        "before_a50_cache_hit": before.get("a50", {}).get("cache_hit_second"),
        "after_a50_cache_hit": after.get("a50", {}).get("cache_hit_second"),
    }


def _soak(duration_hours: int, interval_seconds: int) -> Dict[str, Any]:
    end_at = time.time() + duration_hours * 3600
    runs: List[Dict[str, Any]] = []
    while time.time() < end_at:
        runs.append(_single_run())
        if time.time() + interval_seconds >= end_at:
            break
        time.sleep(max(interval_seconds, 1))
    return {"mode": "soak", "runs": runs, "summary": _summarize_payload(runs)}


def _summarize_payload(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not runs:
        return {"count": 0}
    elapsed = [r.get("elapsed_ms", 0) for r in runs]
    cache_hits = [1 if r.get("a50", {}).get("cache_hit_second") else 0 for r in runs]
    empty_ratios = [r.get("global", {}).get("empty_value_ratio", 1.0) for r in runs]
    return {
        "count": len(runs),
        "elapsed_p50_ms": int(statistics.median(elapsed)),
        "elapsed_p95_ms": int(statistics.quantiles(elapsed, n=20)[18]) if len(elapsed) >= 20 else max(elapsed),
        "a50_cache_hit_ratio": round(sum(cache_hits) / len(cache_hits), 4),
        "empty_value_ratio_avg": round(sum(empty_ratios) / len(empty_ratios), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["before", "after", "soak"], help="run mode")
    parser.add_argument("--output", help="output json path")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--metrics", choices=["a50_cache"])
    parser.add_argument("--summarize", help="summarize soak file")
    parser.add_argument("--duration-hours", type=int, default=24)
    parser.add_argument("--interval-seconds", type=int, default=300)
    args = parser.parse_args()

    if args.compare:
        payload = _compare(args.compare[0], args.compare[1])
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.summarize:
        data = json.loads(Path(args.summarize).read_text(encoding="utf-8"))
        runs = data.get("runs", [])
        print(json.dumps(_summarize_payload(runs), ensure_ascii=False, indent=2))
        return

    if args.mode == "soak":
        payload = _soak(args.duration_hours, args.interval_seconds)
    else:
        payload = _single_run()
        if args.metrics == "a50_cache":
            payload = {
                "a50_cache_hit_ratio": 1.0 if payload.get("a50", {}).get("cache_hit_second") else 0.0,
                "cache_age_ms": payload.get("a50", {}).get("cache_age_ms"),
                "source_stage": "cache" if payload.get("a50", {}).get("cache_hit_second") else "primary",
            }

    if args.output:
        _write_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
