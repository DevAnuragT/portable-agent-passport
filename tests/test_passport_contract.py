import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PassportContractTests(unittest.TestCase):
    def test_required_root_files_exist(self) -> None:
        for relative_path in (
            "agent.yaml", "SOUL.md", "EXPLAINABILITY.md", "DUTIES.md", "AGENTS.md",
            "tools/run_agent.py", "tools/verify_passport.py", "skills/portability/SKILL.md",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_agent_name_is_valid(self) -> None:
        text = (ROOT / "agent.yaml").read_text()
        self.assertIn("spec_version: 0.1.0", text)
        match = re.search(r"^name:\s*([^\s]+)$", text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

    def test_explainability_has_required_headings_and_paragraphs(self) -> None:
        text = (ROOT / "EXPLAINABILITY.md").read_text()
        headings = [line.removeprefix("# ").lower() for line in text.splitlines() if line.startswith("# ")]
        required = (
            ("decision", "reasoning", "how it decides"),
            ("data source", "input", "data used"),
            ("limitation", "constraint", "known issue"),
        )
        for words in required:
            self.assertTrue(any(any(word in heading for word in words) for heading in headings), words)
        for section in text.split("\n# "):
            self.assertGreaterEqual(section.count("."), 2, section.splitlines()[0])

    def test_maker_and_checker_are_not_on_one_line(self) -> None:
        for relative_path in ("DUTIES.md", "AGENTS.md"):
            lines = (ROOT / relative_path).read_text().splitlines()
            self.assertFalse(any("maker" in line.lower() and "checker" in line.lower() for line in lines))


if __name__ == "__main__":
    unittest.main()
