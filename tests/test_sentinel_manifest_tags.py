"""Sentinel bundle metadata on the four sentiment tools in tools_manifest.json."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SENTINEL_TOOL_IDS = [
    "tool_fetch_limit_up_stocks",
    "tool_fetch_a_share_fund_flow",
    "tool_fetch_northbound_flow",
    "tool_fetch_sector_data",
]


class TestSentinelManifestTags(unittest.TestCase):
    def test_sentinel_tools_tagged_and_grouped(self):
        data = json.loads((ROOT / "config/tools_manifest.json").read_text(encoding="utf-8"))
        tools = {t["id"]: t for t in data.get("tools", []) if isinstance(t, dict) and t.get("id")}

        for tool_id in SENTINEL_TOOL_IDS:
            self.assertIn(tool_id, tools, msg=f"missing tool {tool_id}")
            t = tools[tool_id]
            self.assertTrue(t.get("sentinel_bundle"), msg=f"{tool_id} missing sentinel_bundle")
            self.assertEqual(t.get("skill_hint"), "market-sentinel", msg=f"{tool_id} skill_hint mismatch")

        self.assertEqual(tools["tool_fetch_limit_up_stocks"]["tool_group"], "market_sentiment")
        self.assertEqual(tools["tool_fetch_sector_data"]["tool_group"], "market_structure")
        self.assertEqual(tools["tool_fetch_northbound_flow"]["tool_group"], "primary_fund_flow")
        self.assertEqual(tools["tool_fetch_a_share_fund_flow"]["tool_group"], "primary_fund_flow")


if __name__ == "__main__":
    unittest.main()
