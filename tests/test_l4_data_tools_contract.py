from __future__ import annotations

from unittest.mock import patch

from plugins.analysis.l4_data_tools import tool_l4_pe_ttm_percentile, tool_l4_valuation_context


def test_l4_valuation_context_meta():
    fake = {
        "success": True,
        "data": {"pe": 12.3, "pb": 1.1, "roe": 0.15},
    }

    with patch(
        "plugins.analysis.l4_data_tools.fetch_stock_valuation_snapshot_view",
        return_value=fake,
    ):
        out = tool_l4_valuation_context("600519", trade_date="2026-05-01")
    assert out["success"]
    assert out["_meta"]["data_layer"] == "L4_data"
    assert out["_meta"]["schema_name"] == "valuation_context_v1"
    assert "note" in out["data"]
    assert "建议" not in str(out["data"].get("note"))


def test_l4_pe_ttm_percentile_mocked():
    pts = [
        {"report_date": "2020-03-31", "pe_ttm": 30.0},
        {"report_date": "2021-03-31", "pe_ttm": 40.0},
        {"report_date": "2022-03-31", "pe_ttm": 35.0},
        {"report_date": "2023-03-31", "pe_ttm": 32.0},
        {"report_date": "2024-03-31", "pe_ttm": 28.0},
        {"report_date": "2025-03-31", "pe_ttm": 25.0},
        {"report_date": "2025-09-30", "pe_ttm": 22.0},
        {"report_date": "2025-12-31", "pe_ttm": 20.0},
    ]
    fake = {"success": True, "points": pts, "error": None}
    with patch("plugins.analysis.l4_data_tools.fetch_stock_pe_ttm_timeseries", return_value=fake):
        out = tool_l4_pe_ttm_percentile("600519", window_years=10)
    assert out["_meta"]["schema_name"] == "pe_ttm_percentile_band_v1"
    assert out["data"]["sample_size"] >= 8
    assert out["data"]["percentile_0_100"] is not None
