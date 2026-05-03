from __future__ import annotations

from plugins.utils.catalog_digest_tool import tool_plugin_catalog_digest


def test_tool_plugin_catalog_digest():
    out = tool_plugin_catalog_digest()
    assert out["success"]
    d = out["data"]
    assert d.get("registry_schema_version")
    assert "global_index_spot" in (d.get("source_chains") or {})
    assert isinstance(d.get("screenable_factor_ids"), list)
    assert d.get("manifest_tool_count", 0) > 0
