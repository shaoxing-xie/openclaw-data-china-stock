import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestMacroManifestTags(unittest.TestCase):
    def test_macro_tool_tags(self):
        data = json.loads((ROOT / "config/tools_manifest.json").read_text(encoding="utf-8"))
        tools = {t["id"]: t for t in data.get("tools", []) if isinstance(t, dict) and t.get("id")}

        self.assertEqual(tools["tool_fetch_macro_data"]["tool_group"], "primary_macro")
        self.assertTrue(tools["tool_fetch_macro_data"]["recommended"])
        self.assertEqual(tools["tool_fetch_macro_snapshot"]["tool_group"], "primary_macro")
        self.assertTrue(tools["tool_fetch_macro_snapshot"]["recommended"])

        self.assertEqual(tools["tool_fetch_macro_commodities"]["scope"], "legacy")
        self.assertFalse(tools["tool_fetch_macro_commodities"]["recommended"])

        compat_ids = [
            "tool_fetch_macro_pmi",
            "tool_fetch_macro_cx_pmi",
            "tool_fetch_macro_cx_services_pmi",
            "tool_fetch_macro_enterprise_boom",
            "tool_fetch_macro_lpi",
            "tool_fetch_macro_cpi",
            "tool_fetch_macro_ppi",
            "tool_fetch_macro_m2",
            "tool_fetch_macro_social_financing",
            "tool_fetch_macro_new_credit",
            "tool_fetch_macro_lpr",
            "tool_fetch_macro_fx_reserves",
            "tool_fetch_macro_gdp",
            "tool_fetch_macro_industrial_value",
            "tool_fetch_macro_fixed_asset",
            "tool_fetch_macro_leverage",
            "tool_fetch_macro_exports_imports",
            "tool_fetch_macro_trade_balance",
            "tool_fetch_macro_exports_yoy",
            "tool_fetch_macro_unemployment",
            "tool_fetch_macro_tax_receipts",
        ]
        for tool_id in compat_ids:
            self.assertEqual(tools[tool_id]["scope"], "china_macro_analyst")
            self.assertEqual(tools[tool_id]["tool_group"], "macro_compat")
            self.assertFalse(tools[tool_id]["recommended"])


if __name__ == "__main__":
    unittest.main()

