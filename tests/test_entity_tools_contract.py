from __future__ import annotations

import pandas as pd
import pytest

from plugins.data_collection.entity.entity_tools import (
    tool_batch_resolve_symbol,
    tool_get_entity_meta,
    tool_get_etf_holdings,
    tool_resolve_symbol,
)


def test_resolve_stock_sh():
    out = tool_resolve_symbol("sh600519")
    assert out["success"]
    d = out["data"]
    assert d["canonical_code"] == "600519"
    assert d["entity_type"] == "stock"
    assert out["_meta"]["data_layer"] == "L2_entity"


def test_resolve_etf():
    out = tool_resolve_symbol("510300")
    d = out["data"]
    assert d["canonical_code"] == "510300"
    assert d["entity_type"] == "etf"


def test_resolve_index_long_digits():
    out = tool_resolve_symbol("00030010")
    d = out["data"]
    assert d["entity_type"] == "index"
    assert d["canonical_code"] == "000300"


def test_batch_resolve():
    out = tool_batch_resolve_symbol("600519,510300")
    assert out["success"]
    assert out["data"]["count"] == 2


def test_get_entity_meta_ok_master_meta():
    out = tool_get_entity_meta("510300")
    assert out["success"]
    assert out["quality_status"] == "ok"
    assert out["data"]["name"] == "沪深300ETF"


def test_get_entity_meta_unknown_name_degraded():
    out = tool_get_entity_meta("601633")
    assert out["success"]
    assert out["quality_status"] == "degraded"
    assert out["data"].get("name") in (None, "")


def test_get_etf_holdings_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_hold(symbol: str, date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "股票代码": "600519",
                    "股票名称": "贵州茅台",
                    "占净值比例": 5.1,
                    "季度": "2024年1季度股票投资明细",
                }
            ]
        )

    monkeypatch.setattr("akshare.fund_portfolio_hold_em", fake_hold)
    out = tool_get_etf_holdings("510300", max_rows=10)
    assert out["success"]
    assert out["quality_status"] == "ok"
    assert out["data"]["count"] == 1
    assert out["data"]["items"][0]["stock_code"] == "600519"


def test_get_etf_holdings_rejects_non_etf_code():
    out = tool_get_etf_holdings("600519")
    assert out["success"] is False
    assert out["quality_status"] == "degraded"
