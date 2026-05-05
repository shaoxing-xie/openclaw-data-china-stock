"""plugin_data_registry：动态 tie-break（默认关）。"""

from __future__ import annotations

from plugins.utils import plugin_data_registry as reg


def test_dynamic_priority_off_preserves_catalog_merge():
    merged, meta = reg.merge_global_index_spot_priority(["fmp", "yfinance", "sina"])
    assert meta.get("merge_mode") == "catalog_first_then_config_remainder"
    assert merged[0] == "yfinance"
    dp = meta.get("dynamic_priority") or {}
    assert dp.get("enabled") is False


def test_dynamic_tie_break_reorders_when_enabled(monkeypatch):
    monkeypatch.setattr(
        reg,
        "_load_source_priority_config",
        lambda: {"dynamic_priority_enabled": True, "adjustment_mode": "tie_break_only"},
    )
    monkeypatch.setattr(
        reg,
        "_rollup_latest_success_rates",
        lambda _ids: {"yfinance": 0.1, "fmp": 0.95, "sina": 0.5},
    )

    merged, meta = reg.merge_global_index_spot_priority(["yfinance", "fmp", "sina"])
    assert merged[0] == "fmp"
    assert meta.get("dynamic_priority", {}).get("applied") is True
