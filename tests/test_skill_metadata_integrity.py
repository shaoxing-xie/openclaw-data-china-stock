import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

REQUIRED_FRONTMATTER = ["name:", "description:", "version:", "author:", "tags:", "triggers:"]
REQUIRED_SECTIONS = [
    "## 目标",
    "## 输入",
    "## 强制规则",
    "## 依赖工具",
    "## 通用输出字段",
]

SKILL_NAMES = [
    "china-macro-analyst",
    "technical-analyst",
    "market-scanner",
    "fund-flow-analyst",
    "strategy-backtester",
    "fundamental-analyst",
]


class TestSkillMetadataIntegrity(unittest.TestCase):
    def test_required_files_exist(self):
        for skill in SKILL_NAMES:
            base = SKILLS_DIR / skill
            self.assertTrue((base / "SKILL.md").exists(), msg=f"{skill}/SKILL.md missing")
            self.assertTrue((base / "README.md").exists(), msg=f"{skill}/README.md missing")

    def test_frontmatter_and_sections(self):
        for skill in SKILL_NAMES:
            content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
            for marker in REQUIRED_FRONTMATTER:
                self.assertIn(marker, content, msg=f"{skill} missing frontmatter marker: {marker}")
            self.assertTrue(
                ("## 输出（固定结构）" in content) or ("## 输出（固定四段）" in content),
                msg=f"{skill} missing output section",
            )
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, content, msg=f"{skill} missing section: {section}")


if __name__ == "__main__":
    unittest.main()

