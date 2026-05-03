"""Contract: tool_etf_rotation_research _meta aligns with docs/data_model/meta_contract.md."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def _patched_rotation(monkeypatch):
    """Avoid upstream calls; return minimal successful shapes."""
    base = {"success": True, "quality_status": "ok", "data": {"trend_score": 1.0}, "attempts": []}

    def _share(**_kwargs):
        return dict(base)

    def _sector(**_kwargs):
        return dict(base)

    with (
        patch("plugins.analysis.etf_rotation_research.tool_calculate_share_trend", side_effect=_share),
        patch("plugins.analysis.etf_rotation_research.tool_calculate_sector_breadth", side_effect=_sector),
        patch("plugins.analysis.etf_rotation_research.tool_calculate_sector_leadership", side_effect=_sector),
        patch("plugins.analysis.etf_rotation_research.tool_calculate_sector_momentum_v2", side_effect=_sector),
    ):
        yield


def test_etf_rotation_research_meta_contract(_patched_rotation):
    from plugins.analysis.etf_rotation_research import tool_etf_rotation_research

    out = tool_etf_rotation_research(etf_pool="510300", top_k=2, trade_date="2026-05-01")
    assert out.get("success") is True
    meta = out.get("_meta") or {}
    assert meta.get("data_layer") == "L3_aggregate"
    assert meta.get("schema_name") == "rotation_feature_aggregate_v1"
    assert "decision_" not in str(meta.get("schema_name", ""))
    assert meta.get("task_id") == "etf-rotation-research"
    assert "tool_calculate_share_trend" in (meta.get("source_tools") or [])
