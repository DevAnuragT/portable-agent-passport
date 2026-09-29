import tempfile
from pathlib import Path
import unittest

from agent_passport.audit import audit_agent


class AuditTests(unittest.TestCase):
    def test_current_repository_passes_baseline(self) -> None:
        result = audit_agent(Path(__file__).parents[2])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["error_count"], 0)

    def test_missing_files_are_explainable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = audit_agent(directory)
        self.assertEqual(result["status"], "fail")
        self.assertGreaterEqual(result["error_count"], 6)
        self.assertTrue(all("fix" in finding for finding in result["findings"]))


if __name__ == "__main__":
    unittest.main()
