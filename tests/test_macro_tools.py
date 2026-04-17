import unittest
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.data_collection.macro import tools as macro_tools
from plugins.data_collection.macro.constants import (
    ADJACENT_LEGACY_MACRO_TOOLS,
    ANALYST_COMPAT_TOOLS,
    PRIMARY_MACRO_TOOLS,
    TOOL_TO_DATASET,
)


class TestMacroTools(unittest.TestCase):
    @patch("plugins.data_collection.macro.tools.AKShareMacroWrapper.fetch")
    def test_tool_fetch_macro_data_contract(self, mock_fetch):
        mock_fetch.return_value = {
            "success": True,
            "data": [{"日期": "2026-03", "值": 1.2}],
            "attempt": 1,
            "error": None,
            "error_code": None,
        }
        res = macro_tools.tool_fetch_macro_data(dataset="cpi", latest_only=True)
        self.assertTrue(res["success"])
        self.assertIn("data", res)
        self.assertIn("source", res)
        self.assertIn("staleness_days", res)
        self.assertIsNone(res["error"])

    def test_tool_fetch_macro_data_validation(self):
        res = macro_tools.tool_fetch_macro_data(dataset="unknown_dataset")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["error_code"], "VALIDATION_ERROR")

    @patch("plugins.data_collection.macro.tools.tool_fetch_macro_data")
    def test_tool_fetch_macro_snapshot(self, mock_fetch):
        mock_fetch.return_value = {
            "success": True,
            "data": {"records": [{"date": "2026-03", "value": 1}]},
        }
        res = macro_tools.tool_fetch_macro_snapshot()
        self.assertTrue(res["success"])
        self.assertIn("growth", res["data"])
        self.assertIn("inflation", res["data"])
        self.assertIn("credit", res["data"])

    @patch("plugins.data_collection.macro.tools.AKShareMacroWrapper.fetch")
    def test_latest_only_returns_newest_by_date(self, mock_fetch):
        mock_fetch.return_value = {
            "success": True,
            "data": [
                {"月份": "2024年12月份", "值": 1},
                {"月份": "2025年01月份", "值": 2},
            ],
            "attempt": 1,
            "error": None,
            "error_code": None,
        }
        res = macro_tools.tool_fetch_macro_data(dataset="cpi", latest_only=True)
        self.assertEqual(res["data"]["records"][0]["月份"], "2025年01月份")

    @patch("plugins.data_collection.macro.tools.tool_fetch_macro_data")
    def test_compat_tool_accepts_kwargs(self, mock_fetch):
        mock_fetch.return_value = {"success": True, "data": {"records": []}}
        _ = macro_tools.tool_fetch_macro_pmi(latest_only=True, months=6)
        mock_fetch.assert_called_once()

    def test_macro_tool_group_contract(self):
        self.assertEqual(len(ANALYST_COMPAT_TOOLS), 21)
        self.assertEqual(set(ANALYST_COMPAT_TOOLS), set(TOOL_TO_DATASET.keys()))
        self.assertEqual(set(PRIMARY_MACRO_TOOLS), {"tool_fetch_macro_data", "tool_fetch_macro_snapshot"})
        self.assertIn("tool_fetch_macro_commodities", ADJACENT_LEGACY_MACRO_TOOLS)


if __name__ == "__main__":
    unittest.main()

