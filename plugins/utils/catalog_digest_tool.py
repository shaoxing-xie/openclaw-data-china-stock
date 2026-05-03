"""
Read-only digest of factor_registry + tools manifest size (Phase 4 / SKILL Phase C observability).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from plugins.utils.plugin_data_registry import list_screenable_factor_ids, load_registry

_REPO_ROOT = Path(__file__).resolve().parents[2]


def tool_plugin_catalog_digest(**_: Any) -> Dict[str, Any]:
    """
    Return registry schema_version, source_chains summary, screenable factors, manifest tool count.
    """
    reg = load_registry()
    chains = reg.get("source_chains") or {}
    digest: Dict[str, Any] = {}
    if isinstance(chains, dict):
        for k, v in chains.items():
            if isinstance(v, dict):
                digest[str(k)] = {"provider_tags": v.get("provider_tags"), "description": v.get("description")}

    manifest_path = _REPO_ROOT / "config" / "tools_manifest.json"
    tool_count = 0
    if manifest_path.is_file():
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            tools = raw.get("tools") if isinstance(raw, dict) else None
            tool_count = len(tools) if isinstance(tools, list) else 0
        except Exception:
            tool_count = -1

    return {
        "success": True,
        "message": "catalog_digest ok",
        "quality_status": "ok",
        "_meta": {
            "schema_name": "plugin_catalog_digest_v1",
            "schema_version": "1.0.0",
            "data_layer": "L2_entity",
            "task_id": "plugin-catalog-digest",
            "generated_at": datetime.now().isoformat(),
            "lineage_refs": ["load_registry", "config/tools_manifest.json"],
        },
        "data": {
            "registry_schema_version": reg.get("schema_version"),
            "registry_path": reg.get("registry_path"),
            "registry_note": reg.get("registry_note"),
            "screenable_factor_ids": list_screenable_factor_ids(),
            "source_chains": digest,
            "manifest_tool_count": tool_count,
        },
    }
