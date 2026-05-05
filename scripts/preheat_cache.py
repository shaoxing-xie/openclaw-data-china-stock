#!/usr/bin/env python3
"""
缓存预热：调用 tool_runner 预热常用工具，摘要写入 data/meta/preheat_result.json。

Cron 应在 shell 中加载 ~/.openclaw/.env（set -a; source ...），本脚本不替代该语义。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_tool_subprocess(tool_name: str, params: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    root = _root()
    runner = root / "tool_runner.py"
    py = sys.executable
    cmd = [py, str(runner), tool_name, json.dumps(params, ensure_ascii=False)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=None,
        )
        raw = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        if proc.returncode != 0:
            return {"success": False, "error": f"exit_{proc.returncode}", "stderr_tail": (proc.stderr or "")[-800:]}
        try:
            return json.loads(raw) if raw else {"success": False, "error": "empty_output"}
        except json.JSONDecodeError:
            return {"success": False, "error": "invalid_json", "raw_tail": raw[-800:]}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _load_config(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required for preheat_config.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenClaw data plugin cache preheat")
    ap.add_argument(
        "--config",
        type=str,
        default=str(_root() / "config" / "preheat_config.yaml"),
        help="preheat YAML path",
    )
    args = ap.parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        print(json.dumps({"success": False, "error": f"missing_config:{cfg_path}"}, ensure_ascii=False))
        return 2

    cfg = _load_config(cfg_path)
    block = cfg.get("preheat") if isinstance(cfg.get("preheat"), dict) else {}
    if not block.get("enabled", False):
        print(json.dumps({"success": True, "skipped": True, "reason": "preheat_disabled"}, ensure_ascii=False))
        return 0

    targets = block.get("targets") or []
    opts = block.get("options") if isinstance(block.get("options"), dict) else {}
    timeout_s = int(opts.get("timeout_seconds") or 120)
    parallel = bool(opts.get("parallel", True))
    max_workers = max(1, int(opts.get("max_workers") or 4))

    results: Dict[str, Any] = {}

    def _one(t: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        name = str(t.get("name") or t.get("tool") or "unknown")
        tool = str(t.get("tool") or "").strip()
        params = t.get("params") if isinstance(t.get("params"), dict) else {}
        if not tool:
            return name, {"success": False, "error": "missing_tool"}
        out = _run_tool_subprocess(tool, params, timeout_s)
        ok = bool(out.get("success", True)) if isinstance(out, dict) else False
        return name, {
            "success": ok,
            "memory_cache_hit": bool(out.get("_memory_cache_hit")) if isinstance(out, dict) else False,
            "cache_hit": bool(out.get("_cache_hit")) if isinstance(out, dict) else False,
            "error": out.get("error") if isinstance(out, dict) else None,
        }

    if parallel and len(targets) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_one, t): t for t in targets if isinstance(t, dict)}
            for fu in as_completed(futs):
                name, payload = fu.result()
                results[name] = payload
    else:
        for t in targets:
            if isinstance(t, dict):
                name, payload = _one(t)
                results[name] = payload

    summary = {
        "_meta": {
            "schema_name": "preheat_result_v1",
            "schema_version": "1.0.0",
            "data_layer": "L4",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "quality_status": "ok",
        },
        "results": results,
        "success_count": sum(1 for r in results.values() if isinstance(r, dict) and r.get("success")),
        "total": len(results),
    }

    out_path = _root() / "data" / "meta" / "preheat_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": True, "written": str(out_path), **summary["_meta"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
