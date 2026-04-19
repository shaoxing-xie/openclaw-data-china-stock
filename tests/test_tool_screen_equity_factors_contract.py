"""契约：tool_screen_equity_factors 成功响应字段与 JSON Schema 对齐（不强制联网）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _schema() -> dict:
    p = ROOT / "docs" / "schemas" / "tool_screen_equity_factors.schema.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _validate_success_payload(instance: dict, schema: dict) -> None:
    req = schema.get("required", [])
    for k in req:
        assert k in instance, f"missing required key {k}"
    assert isinstance(instance.get("success"), bool)
    assert isinstance(instance.get("degraded"), bool)
    ch = instance.get("config_hash")
    assert isinstance(ch, str) and len(ch) >= 8
    data = instance.get("data")
    if instance.get("success") and data is not None:
        assert isinstance(data, list)
        for row in data:
            assert "symbol" in row and "score" in row and "factors" in row


def test_contract_schema_file_exists() -> None:
    schema = _schema()
    assert schema.get("title")


def test_tool_screen_equity_factors_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    from plugins.analysis import equity_factor_screening as mod
    from plugins.analysis.sw_industry_mapping import load_sw_level1_mapping

    load_sw_level1_mapping.cache_clear()

    def fake_hist(**_: object) -> dict:
        return {
            "success": True,
            "data": {
                "stock_code": "600000",
                "klines": [
                    {"close": 10.0, "date": "2026-01-01"},
                    {"close": 10.1, "date": "2026-01-02"},
                    {"close": 10.0, "date": "2026-01-03"},
                    {"close": 9.9, "date": "2026-01-04"},
                    {"close": 9.8, "date": "2026-01-05"},
                    {"close": 9.5, "date": "2026-01-06"},
                ],
                "count": 6,
            },
        }

    def fake_fund_flow(**_: object) -> dict:
        return {
            "success": True,
            "records": [
                {"代码": "600000", "名称": "浦发银行", "所属行业": "银行", "今日主力净流入-净额": 1.2e7},
            ],
        }

    def fake_sector(**_: object) -> dict:
        return {
            "status": "success",
            "all_data": [{"sector_name": "银行", "change_percent": 0.5}],
        }

    monkeypatch.setattr(
        "plugins.data_collection.stock.fetch_historical.tool_fetch_stock_historical",
        fake_hist,
    )
    monkeypatch.setattr(
        "plugins.data_collection.a_share_fund_flow.tool_fetch_a_share_fund_flow",
        fake_fund_flow,
    )
    monkeypatch.setattr(
        "plugins.data_collection.sector.tool_fetch_sector_data",
        fake_sector,
    )

    def fake_constituents(*_: object, **__: object) -> dict:
        return {
            "success": True,
            "data": [{"成分券代码": "600000", "成分券名称": "浦发银行"}],
        }

    monkeypatch.setattr(
        "plugins.data_collection.stock.reference_p1.tool_fetch_index_constituents",
        fake_constituents,
    )

    out = mod.tool_screen_equity_factors(
        universe="hs300",
        factors=["reversal_5d", "fund_flow_3d", "sector_momentum_5d"],
        top_n=3,
        max_universe_size=5,
        max_concurrent_fetch=2,
    )
    schema = _schema()
    _validate_success_payload(out, schema)
    assert out["success"] is True
    assert out["data"][0]["symbol"] == "600000"
