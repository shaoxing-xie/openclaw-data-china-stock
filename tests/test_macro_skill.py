import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestMacroSkillAssets(unittest.TestCase):
    def test_skill_file_has_required_sections(self):
        content = (ROOT / "skills/china-macro-analyst/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("输出（固定四段）", content)
        self.assertIn("风险与反证", content)
        self.assertIn("insufficient_evidence", content)

    def test_macro_config_has_quadrant_rules(self):
        content = (ROOT / "skills/china-macro-analyst/config/macro_config.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("quadrant_rules:", content)
        self.assertIn("output_policy:", content)
        self.assertIn("allow_execution_instruction: false", content)


if __name__ == "__main__":
    unittest.main()

