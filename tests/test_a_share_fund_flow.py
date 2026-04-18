"""Tests for tool_fetch_a_share_fund_flow (mocked AkShare)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from plugins.data_collection import a_share_fund_flow as mod


class TestAShareFundFlow(unittest.TestCase):
    def test_invalid_query_kind(self):
        r = mod.tool_fetch_a_share_fund_flow(query_kind="nope")
        self.assertFalse(r["success"])
        self.assertIn("invalid query_kind", r.get("error", ""))

    def test_stock_history_invalid_code(self):
        r = mod.tool_fetch_a_share_fund_flow(query_kind="stock_history", stock_code="12")
        self.assertFalse(r["success"])
        self.assertIn("stock_code", r.get("error", ""))

    @patch.object(mod, "ak")
    def test_market_history_tail_max_days(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_fund_flow_industry.return_value = pd.DataFrame(
            [{"净额": "1亿"}, {"净额": "-0.5亿"}]
        )
        mock_ak.stock_fund_flow_concept.return_value = pd.DataFrame(
            [{"净额": "0.2亿"}, {"净额": "-0.1亿"}]
        )
        r = mod.tool_fetch_a_share_fund_flow(query_kind="market_history", max_days=5)
        self.assertTrue(r["success"])
        self.assertEqual(r["query_kind"], "market_history")
        self.assertGreaterEqual(len(r["records"]), 1)
        self.assertEqual(r.get("metric_semantics"), "proxy_from_ths_industry_aggregate")

    @patch.object(mod, "ak")
    def test_stock_rank_ths_primary(self, mock_ak: MagicMock) -> None:
        def ths_ok(*_a: object, **_k: object) -> pd.DataFrame:
            return pd.DataFrame([{"代码": "600000", "名称": "浦发银行", "净流入": 1.0}])

        mock_ak.stock_fund_flow_individual.side_effect = ths_ok
        r = mod.tool_fetch_a_share_fund_flow(query_kind="stock_rank", limit=10)
        self.assertTrue(r["success"])
        self.assertEqual(r["query_kind"], "stock_rank")
        self.assertFalse(r.get("used_fallback"))
        self.assertEqual(r["records"][0]["代码"], "600000")
        mock_ak.stock_fund_flow_individual.assert_called()
        mock_ak.stock_individual_fund_flow_rank.assert_not_called()

    @patch.object(mod, "ak")
    @patch.object(mod, "ENABLE_EASTMONEY_FALLBACK", True)
    def test_stock_rank_preference_eastmoney_first(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_individual_fund_flow_rank.return_value = pd.DataFrame(
            [{"代码": "000001", "名称": "平安"}]
        )
        mock_ak.stock_fund_flow_individual.side_effect = RuntimeError("ths down")
        r = mod.tool_fetch_a_share_fund_flow(
            query_kind="stock_rank",
            provider_preference="eastmoney",
            limit=5,
        )
        self.assertTrue(r["success"])
        self.assertFalse(r.get("used_fallback"))
        mock_ak.stock_individual_fund_flow_rank.assert_called()
        # THS should not run when EM succeeds first
        mock_ak.stock_fund_flow_individual.assert_not_called()

    @patch.object(mod, "ak")
    def test_sector_rank_industry_fallback_em_to_ths(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_fund_flow_industry.return_value = pd.DataFrame(
            [{"名称": "银行", "净额": 0.1}]
        )
        r = mod.tool_fetch_a_share_fund_flow(
            query_kind="sector_rank",
            sector_type="industry",
            rank_window="immediate",
        )
        self.assertTrue(r["success"])
        self.assertFalse(r.get("used_fallback"))
        self.assertEqual(r["records"][0]["名称"], "银行")

    @patch.object(mod, "EM_HTTP_AVAILABLE", False)
    @patch.object(mod, "ak")
    def test_stock_history_lookback(self, mock_ak: MagicMock) -> None:
        df = pd.DataFrame(
            {
                "日期": pd.date_range("2024-01-01", periods=40, freq="D"),
                "主力": range(40),
            }
        )
        mock_ak.stock_individual_fund_flow.return_value = df
        r = mod.tool_fetch_a_share_fund_flow(
            query_kind="stock_history",
            stock_code="600000",
            lookback_days=5,
        )
        self.assertTrue(r["success"])
        self.assertEqual(len(r["records"]), 5)

    @patch.object(mod, "THS_BD_LIMITED_AVAILABLE", False)
    @patch.object(mod, "EM_HTTP_AVAILABLE", False)
    @patch.object(mod, "ak")
    def test_big_deal_filter_by_code_column(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_fund_flow_big_deal.return_value = pd.DataFrame(
            [
                {"股票代码": "600000", "v": 1},
                {"股票代码": "000001", "v": 2},
            ]
        )
        r = mod.tool_fetch_a_share_fund_flow(
            query_kind="big_deal",
            big_deal_stock_code="600000",
            limit=50,
        )
        self.assertTrue(r["success"])
        self.assertEqual(len(r["records"]), 1)
        self.assertEqual(r["records"][0]["股票代码"], "600000")

    @patch.object(mod, "THS_BD_LIMITED_AVAILABLE", False)
    @patch.object(mod, "ak")
    @patch.object(mod, "ENABLE_EASTMONEY_FALLBACK", False)
    def test_big_deal_prefers_eastmoney_proxy(
        self, mock_ak: MagicMock
    ) -> None:
        mock_ak.stock_fund_flow_big_deal.return_value = pd.DataFrame(
            [{"代码": "000001", "名称": "平安", "今日大单净流入-净额": 1.0}]
        )
        r = mod.tool_fetch_a_share_fund_flow(query_kind="big_deal", limit=5)
        self.assertTrue(r["success"])
        self.assertIn("akshare", r["source"])
        self.assertFalse(r.get("used_fallback"))
        mock_ak.stock_fund_flow_big_deal.assert_called_once()

    @patch.object(mod, "EM_HTTP_AVAILABLE", False)
    @patch.object(mod, "ak")
    def test_main_force_rank(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_main_fund_flow.return_value = pd.DataFrame([{"a": 1}])
        r = mod.tool_fetch_a_share_fund_flow(
            query_kind="main_force_rank",
            main_force_symbol="全部股票",
        )
        self.assertTrue(r["success"])
        mock_ak.stock_main_fund_flow.assert_called_once()

    @patch.object(mod, "ak")
    def test_sector_drill_summary_and_hist(self, mock_ak: MagicMock) -> None:
        mock_ak.stock_sector_fund_flow_summary.return_value = pd.DataFrame([{"代码": "1"}])
        mock_ak.stock_sector_fund_flow_hist.return_value = pd.DataFrame([{"日期": "2024-01-01"}])
        r = mod.tool_fetch_a_share_fund_flow(
            query_kind="sector_drill",
            sector_name="银行",
            include_hist=True,
            drill_kind="industry",
        )
        self.assertTrue(r["success"])
        self.assertIn("summary", r)
        self.assertIn("history", r)
        mock_ak.stock_sector_fund_flow_hist.assert_called_once()


if __name__ == "__main__":
    unittest.main()
