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
        self.assertIn("path: tools/run_agent.py", text)
        self.assertIn("path: skills/portability/SKILL.md", text)
        match = re.search(r"^name:\s*([^\s]+)$", text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

    def test_explainability_has_required_headings_and_paragraphs(self) -> None:
        text = (ROOT / "EXPLAINABILITY.md").read_text()
        for heading, words in {
            "Decision": ("decision", "reasoning", "how it decides"),
            "Inputs": ("data source", "input", "data used"),
            "Limits": ("limitation", "constraint", "known issue"),
        }.items():
            section = text.split(f"# {heading}", 1)[1].split("\n# ", 1)[0]
            self.assertGreaterEqual(section.count("."), 2, heading)
            self.assertTrue(any(word in section.lower() for word in words), heading)

    def test_maker_and_checker_are_not_on_one_line(self) -> None:
        for relative_path in ("DUTIES.md", "AGENTS.md"):
            lines = (ROOT / relative_path).read_text().splitlines()
            self.assertFalse(any("maker" in line.lower() and "checker" in line.lower() for line in lines))


if __name__ == "__main__":
    unittest.main()
