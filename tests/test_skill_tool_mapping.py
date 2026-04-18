import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "tools_manifest.json"
SKILLS_DIR = ROOT / "skills"

SKILL_TOOL_RULES = {
    "technical-analyst": [
        "tool_calculate_technical_indicators",
        "tool_fetch_market_data",
    ],
    "market-scanner": [
        "tool_check_trading_status",
        "tool_fetch_market_data",
        "tool_fetch_sector_data",
        "tool_fetch_a_share_fund_flow",
        "tool_fetch_northbound_flow",
        "tool_fetch_limit_up_stocks",
    ],
    "market-sentinel": [
        "tool_fetch_limit_up_stocks",
        "tool_fetch_a_share_fund_flow",
        "tool_fetch_northbound_flow",
        "tool_fetch_sector_data",
    ],
    "fund-flow-analyst": [
        "tool_fetch_a_share_fund_flow",
        "tool_fetch_northbound_flow",
        "tool_fetch_sector_data",
    ],
    "strategy-backtester": [
        "tool_fetch_market_data",
        "tool_calculate_technical_indicators",
    ],
    "fundamental-analyst": [
        "tool_fetch_stock_financials",
        "tool_fetch_stock_financial_reports",
        "tool_fetch_market_data",
    ],
}


class TestSkillToolMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.tool_ids = {tool["id"] for tool in data["tools"] if isinstance(tool, dict) and "id" in tool}

    def test_skill_declared_tools_exist_in_manifest(self):
        for skill_name, tool_ids in SKILL_TOOL_RULES.items():
            content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for tool_id in tool_ids:
                self.assertIn(tool_id, content, msg=f"{skill_name} does not declare {tool_id}")
                self.assertIn(tool_id, self.tool_ids, msg=f"{tool_id} missing in tools_manifest.json")

    def test_scope_annotations_exist_for_new_skill_tools(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        tools = {t["id"]: t for t in data["tools"] if isinstance(t, dict) and t.get("id")}
        scoped_tools = [
            "tool_calculate_technical_indicators",
            "tool_fetch_market_data",
            "tool_fetch_sector_data",
            "tool_fetch_a_share_fund_flow",
            "tool_fetch_northbound_flow",
            "tool_fetch_limit_up_stocks",
            "tool_fetch_stock_financials",
            "tool_fetch_stock_financial_reports",
            "tool_check_trading_status",
        ]
        for tool_id in scoped_tools:
            self.assertIn("scope", tools[tool_id], msg=f"{tool_id} missing scope")
            self.assertIn("tool_group", tools[tool_id], msg=f"{tool_id} missing tool_group")
            self.assertIn("recommended", tools[tool_id], msg=f"{tool_id} missing recommended")


if __name__ == "__main__":
    unittest.main()

