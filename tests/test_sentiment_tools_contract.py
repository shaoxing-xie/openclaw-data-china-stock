from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from plugins.data_collection import a_share_fund_flow as fund
from plugins.data_collection import northbound
from plugins.data_collection import sector
from plugins.data_collection.limit_up import fetch_limit_up
def test_limit_up_contract_and_metrics():
    em_df = pd.DataFrame(
        [
            {"代码": "000001", "名称": "A", "涨跌幅": 10.0, "连板数": 2, "所属行业": "银行", "炸板次数": 1},
            {"代码": "000002", "名称": "B", "涨跌幅": 9.9, "连板数": 3, "所属行业": "地产", "炸板次数": 0},
            {"代码": "000003", "名称": "C", "涨跌幅": 9.8, "连板数": 1, "所属行业": "银行", "炸板次数": 0},
            {"代码": "000004", "名称": "D", "涨跌幅": 9.7, "连板数": 1, "所属行业": "银行", "炸板次数": 0},
            {"代码": "000005", "名称": "E", "涨跌幅": 9.6, "连板数": 1, "所属行业": "券商", "炸板次数": 0},
        ]
    )
    prev_df = pd.DataFrame([{"代码": "000001", "名称": "A", "涨跌幅": 1.2}, {"代码": "000002", "名称": "B", "涨跌幅": -0.5}])
    strong_df = pd.DataFrame([{"代码": "000001"}] * 20)
    sub_df = pd.DataFrame([{"代码": "000010"}] * 12)

    def fake_pool(func_name: str, _date: str):
        mapping = {
            "stock_zt_pool_em": em_df,
            "stock_zt_pool_previous_em": prev_df,
            "stock_zt_pool_strong_em": strong_df,
            "stock_zt_pool_sub_new_em": sub_df,
        }
        return mapping.get(func_name), None

    with patch.object(fetch_limit_up, "cache_get", return_value=None), patch.object(
        fetch_limit_up, "_fetch_pool_df", side_effect=fake_pool
    ):
        out = fetch_limit_up.tool_fetch_limit_up_stocks(date="20260418")
    assert out["success"] is True
    assert "sentiment_stage" in out
    assert "data_quality" in out
    assert out["limit_up_count"] == 5


def test_fund_flow_market_postprocess():
    raw = {
        "success": True,
        "query_kind": "market_history",
        "source": "akshare.stock_market_fund_flow",
        "records": [{"主力净流入": 10}, {"主力净流入": 20}, {"主力净流入": -5}],
        "attempts": [{"source": "akshare", "ok": True, "message": "ok"}],
        "used_fallback": False,
    }
    with patch.object(fund, "_qk_market_history", return_value=raw):
        out = fund.tool_fetch_a_share_fund_flow(query_kind="market_history", max_days=3)
    assert out["success"] is True
    assert "cumulative" in out
    assert "flow_score" in out
    assert "data_quality" in out


def test_northbound_legacy_fallback_path():
    mock_resp = MagicMock()
    mock_resp.text = '{"data":[["2026-04-18","10","5","5","8","3","5","10"]]}'
    mock_resp.encoding = "utf-8"
    with patch.object(northbound.requests, "get", return_value=mock_resp):
        out = northbound.tool_fetch_northbound_flow(lookback_days=1)
    assert out["success"] is True
    assert out["source"] == "eastmoney.legacy_hsgt"
    assert out["used_fallback"] is True


def test_northbound_tushare_primary_path():
    class _Pro:
        @staticmethod
        def moneyflow_hsgt(**kwargs):
            if "trade_date" in kwargs:
                return pd.DataFrame(
                    [
                        {
                            "trade_date": "20260417",
                            "hgt": "127611.49",
                            "sgt": "170452.49",
                            "north_money": "298063.98",
                            "south_money": "53446.71",
                        }
                    ]
                )
            return pd.DataFrame()

    with patch.object(northbound, "_get_tushare_pro", return_value=_Pro()):
        out = northbound.tool_fetch_northbound_flow(date="2026-04-17", lookback_days=1)
    assert out["success"] is True
    assert out["source"] == "tushare.moneyflow_hsgt"
    assert out["used_fallback"] is False
    assert out["data"]["total_net"] > 0


def test_sector_contract_path():
    names = [f"行业{i}" for i in range(35)]
    sdf = pd.DataFrame(
        {
            "sector_name": names,
            "change_percent": [2.1 - i * 0.05 for i in range(35)],
            "net_inflow": [10 - i * 0.2 for i in range(35)],
        }
    )
    with patch.object(sector, "_fetch_sector_from_ths_industry_summary", return_value=sdf):
        out = sector.tool_fetch_sector_data(sector_type="industry")
    assert out["success"] is True
    assert "rotation_speed_score" in out
    assert "main_line" in out


def test_sector_no_estimation_when_all_failed():
    with patch.object(sector, "_fetch_sector_from_ths_industry_summary", return_value=None), patch.object(
        sector, "_fetch_sector_from_sina", return_value=None
    ), patch.object(sector, "_fetch_sector_data_from_eastmoney", return_value=None), patch.object(
        sector, "_fetch_sector_data_from_akshare", return_value=None
    ), patch.object(
        sector, "cache_get", return_value=None
    ):
        out = sector.tool_fetch_sector_data(sector_type="industry")
    assert out["success"] is False
    assert out.get("error_code") == "UPSTREAM_FETCH_FAILED"
