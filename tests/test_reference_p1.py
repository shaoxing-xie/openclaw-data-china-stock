"""reference_p1 工具 mock 单测（无外网）。"""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd


class TestReferenceP1(unittest.TestCase):
    def test_shareholders_top10(self):
        from plugins.data_collection.stock import reference_p1 as r1

        df = pd.DataFrame({"股东": ["x"], "持股": [1.0]})
        fake = MagicMock()
        fake.stock_main_stock_holder.return_value = df

        with patch.object(r1, "AKSHARE_AVAILABLE", True), patch.object(r1, "ak", fake):
            res = r1.tool_fetch_stock_shareholders("600000", holder_kind="top10")

        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 1)
        fake.stock_main_stock_holder.assert_called_once()

    def test_ipo_declare(self):
        from plugins.data_collection.stock import reference_p1 as r1

        df = pd.DataFrame({"名称": ["a"]})
        fake = MagicMock()
        fake.stock_ipo_declare_em.return_value = df

        with patch.object(r1, "AKSHARE_AVAILABLE", True), patch.object(r1, "ak", fake):
            res = r1.tool_fetch_ipo_calendar(ipo_kind="declare_em")

        self.assertTrue(res["success"])

    def test_index_constituents_csindex(self):
        from plugins.data_collection.stock import reference_p1 as r1

        df = pd.DataFrame({"code": ["600000"]})
        fake = MagicMock()
        fake.index_stock_cons_csindex.return_value = df

        with patch.object(r1, "AKSHARE_AVAILABLE", True), patch.object(r1, "ak", fake):
            res = r1.tool_fetch_index_constituents("000300", include_weight=False)

        self.assertTrue(res["success"])
        fake.index_stock_cons_csindex.assert_called_once_with(symbol="000300")

    def test_index_constituents_strips_extra_digits(self):
        from plugins.data_collection.stock import reference_p1 as r1

        df = pd.DataFrame({"code": ["600000"]})
        fake = MagicMock()
        fake.index_stock_cons_csindex.return_value = df

        with patch.object(r1, "AKSHARE_AVAILABLE", True), patch.object(r1, "ak", fake):
            res = r1.tool_fetch_index_constituents("00030010", include_weight=False)

        self.assertTrue(res["success"])
        fake.index_stock_cons_csindex.assert_called_once_with(symbol="000300")

    def test_research_news(self):
        from plugins.data_collection.stock import reference_p1 as r1

        df = pd.DataFrame({"标题": ["t"]})
        fake = MagicMock()
        fake.stock_news_em.return_value = df

        with patch.object(r1, "AKSHARE_AVAILABLE", True), patch.object(r1, "ak", fake):
            res = r1.tool_fetch_stock_research_news(content_kind="news", stock_code="600000")

        self.assertTrue(res["success"])


if __name__ == "__main__":
    unittest.main()
