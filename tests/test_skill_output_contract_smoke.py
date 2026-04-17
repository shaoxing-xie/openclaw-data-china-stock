import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

EXPECTED_OUTPUT_KEYS = {
    "technical-analyst": [
        "summary",
        "trend",
        "momentum",
        "volatility",
        "pattern_signals",
        "scorecard",
        "risk_counterevidence",
        "evidence",
        "confidence_band",
    ],
    "market-scanner": [
        "market_snapshot",
        "breadth",
        "sector_strength",
        "flow_snapshot",
        "anomaly_watchlist",
        "sentiment_state",
        "playbook",
        "risks",
        "event_window",
        "data_freshness",
    ],
    "fund-flow-analyst": [
        "market_flow",
        "northbound_flow",
        "sector_flow_rank",
        "crowding_signals",
        "continuity_metrics",
        "implications",
        "counterevidence",
        "confidence_band",
    ],
    "strategy-backtester": [
        "strategy_spec",
        "backtest_window",
        "performance",
        "risk_metrics",
        "trade_stats",
        "parameter_sensitivity",
        "limitations",
        "next_experiments",
    ],
    "fundamental-analyst": [
        "profitability",
        "growth",
        "solvency",
        "valuation",
        "peer_delta",
        "composite_score",
        "key_risks",
        "confidence_band",
    ],
}


class TestSkillOutputContractSmoke(unittest.TestCase):
    def test_output_contract_keys_declared(self):
        for skill_name, keys in EXPECTED_OUTPUT_KEYS.items():
            content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for key in keys:
                self.assertIn(f"`{key}`", content, msg=f"{skill_name} missing output key: {key}")


if __name__ == "__main__":
    unittest.main()

