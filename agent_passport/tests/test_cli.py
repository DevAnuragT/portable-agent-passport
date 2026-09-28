import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from agent_passport.cli import main


class CliTests(unittest.TestCase):
    def test_run_emits_json(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["run", "summarise portability", "--runtime", "portable-json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["runtime"], "portable-json")
        self.assertIn("summarise portability", payload["answer"])

    def test_verify_returns_success(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["verify"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(all(item["passed"] for item in payload))


if __name__ == "__main__":
    unittest.main()
