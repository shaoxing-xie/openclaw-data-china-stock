#!/usr/bin/env python3
"""Register dev plugin + skill set into local OpenClaw runtime.

Goals:
- Keep existing registrations intact.
- Ensure OpenClaw uses this development repo for plugin tool discovery.
- Expose repository skills to workspace agents.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


# 插件根目录：默认本脚本所在仓库；若已将插件同步到 ~/.openclaw/extensions/openclaw-data-china-stock，
# 可设置 OPENCLAW_DATA_CHINA_STOCK_ROOT 指向该目录后再运行本脚本。
REPO_ROOT = Path(
    os.environ.get("OPENCLAW_DATA_CHINA_STOCK_ROOT", str(Path(__file__).resolve().parents[1]))
).resolve()
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
PLUGIN_ID = "openclaw-data-china-stock"
PLUGIN_SKILL_NAMES = [
    "china-macro-analyst",
    "technical-analyst",
    "market-scanner",
    "market-sentinel",
    "fund-flow-analyst",
    "strategy-backtester",
    "fundamental-analyst",
]
# 交易助手仓 `skills/` 下的 L4-semantic brief（须与 etf-options-ai-assistant 目录名一致）
ASSISTANT_BRIEF_SKILL_NAMES = [
    "ota-equity-valuation-brief",
    "ota-flow-sentiment-brief",
    "ota-market-regime-brief",
]
ASSISTANT_ROOT = Path(
    os.environ.get("OPENCLAW_ETF_OPTIONS_ASSISTANT_ROOT", "/home/xie/etf-options-ai-assistant")
).resolve()
WORKSPACE_SKILLS = Path.home() / ".openclaw" / "workspaces" / "etf-options-ai-assistant" / "skills"


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


def _ensure_skill_symlink(skill_name: str, skill_repo_root: Path) -> str:
    skill_src = skill_repo_root / "skills" / skill_name
    skill_dst = WORKSPACE_SKILLS / skill_name
    if not skill_src.exists():
        raise FileNotFoundError(f"skill source not found: {skill_src}")

    WORKSPACE_SKILLS.mkdir(parents=True, exist_ok=True)
    if skill_dst.exists() or skill_dst.is_symlink():
        if skill_dst.is_symlink() and skill_dst.resolve() == skill_src.resolve():
            return str(skill_dst)
        if skill_dst.is_dir() and not skill_dst.is_symlink():
            return str(skill_dst)
        skill_dst.unlink(missing_ok=True)
    os.symlink(skill_src, skill_dst)
    return str(skill_dst)


def _ensure_agent_skill_binding(cfg: Dict[str, Any]) -> None:
    agents = cfg.get("agents", {}).get("list", [])
    bind_names = list(PLUGIN_SKILL_NAMES) + list(ASSISTANT_BRIEF_SKILL_NAMES)
    for agent in agents:
        workspace = str(agent.get("workspace", ""))
        if workspace.endswith("/etf-options-ai-assistant"):
            skills: List[str] = agent.setdefault("skills", [])
            for skill_name in bind_names:
                if skill_name not in skills:
                    skills.append(skill_name)


def main() -> int:
    if not OPENCLAW_JSON.exists():
        raise FileNotFoundError(f"openclaw config not found: {OPENCLAW_JSON}")
    cfg = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
    _ensure_plugin_registration(cfg)
    _ensure_agent_skill_binding(cfg)
    OPENCLAW_JSON.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    symlink_paths = [_ensure_skill_symlink(skill_name, REPO_ROOT) for skill_name in PLUGIN_SKILL_NAMES]
    symlink_paths += [
        _ensure_skill_symlink(skill_name, ASSISTANT_ROOT) for skill_name in ASSISTANT_BRIEF_SKILL_NAMES
    ]

    print(
        json.dumps(
            {
                "success": True,
                "openclaw_json": str(OPENCLAW_JSON),
                "plugin_repo_path": str(REPO_ROOT),
                "plugin_manifest": str(REPO_ROOT / "config" / "tools_manifest.json"),
                "plugin_runner": str(REPO_ROOT / "tool_runner.py"),
                "plugin_root_env": os.environ.get("OPENCLAW_DATA_CHINA_STOCK_ROOT"),
                "skill_symlinks": symlink_paths,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

