#!/usr/bin/env python3
"""Register dev plugin + macro skill into local OpenClaw runtime.

Goals:
- Keep existing registrations intact.
- Ensure OpenClaw uses this development repo for plugin tool discovery.
- Expose china-macro-analyst skill to workspace agents.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
PLUGIN_ID = "openclaw-data-china-stock"
SKILL_NAME = "china-macro-analyst"
SKILL_SRC = REPO_ROOT / "skills" / SKILL_NAME
WORKSPACE_SKILLS = Path.home() / ".openclaw" / "workspaces" / "etf-options-ai-assistant" / "skills"
SKILL_DST = WORKSPACE_SKILLS / SKILL_NAME


def _ensure_plugin_registration(cfg: Dict[str, Any]) -> None:
    plugins = cfg.setdefault("plugins", {})
    allow = plugins.setdefault("allow", [])
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)

    load = plugins.setdefault("load", {})
    paths = load.setdefault("paths", [])
    repo_path = str(REPO_ROOT)
    if repo_path not in paths:
        paths.append(repo_path)

    entries = plugins.setdefault("entries", {})
    entry = entries.setdefault(PLUGIN_ID, {})
    entry["enabled"] = True
    entry_cfg = entry.setdefault("config", {})
    entry_cfg["scriptPath"] = str(REPO_ROOT / "tool_runner.py")
    entry_cfg["manifestPath"] = str(REPO_ROOT / "config" / "tools_manifest.json")


def _ensure_skill_symlink() -> None:
    WORKSPACE_SKILLS.mkdir(parents=True, exist_ok=True)
    if SKILL_DST.exists() or SKILL_DST.is_symlink():
        if SKILL_DST.is_symlink() and SKILL_DST.resolve() == SKILL_SRC:
            return
        if SKILL_DST.is_dir() and not SKILL_DST.is_symlink():
            return
        SKILL_DST.unlink(missing_ok=True)
    os.symlink(SKILL_SRC, SKILL_DST)


def _ensure_agent_skill_binding(cfg: Dict[str, Any]) -> None:
    agents = cfg.get("agents", {}).get("list", [])
    for agent in agents:
        workspace = str(agent.get("workspace", ""))
        if workspace.endswith("/etf-options-ai-assistant"):
            skills: List[str] = agent.setdefault("skills", [])
            if SKILL_NAME not in skills:
                skills.append(SKILL_NAME)


def main() -> int:
    if not OPENCLAW_JSON.exists():
        raise FileNotFoundError(f"openclaw config not found: {OPENCLAW_JSON}")
    if not SKILL_SRC.exists():
        raise FileNotFoundError(f"skill source not found: {SKILL_SRC}")

    cfg = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
    _ensure_plugin_registration(cfg)
    _ensure_agent_skill_binding(cfg)
    OPENCLAW_JSON.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _ensure_skill_symlink()

    print(
        json.dumps(
            {
                "success": True,
                "openclaw_json": str(OPENCLAW_JSON),
                "plugin_repo_path": str(REPO_ROOT),
                "plugin_manifest": str(REPO_ROOT / "config" / "tools_manifest.json"),
                "plugin_runner": str(REPO_ROOT / "tool_runner.py"),
                "skill_symlink": str(SKILL_DST),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

