import json
from pathlib import Path
import unittest

from agent_passport.manifest import PassportManifest


class PassportFileTests(unittest.TestCase):
    def test_checked_in_passport_is_valid(self) -> None:
        path = Path(__file__).parents[1] / "passport.json"
        manifest = PassportManifest.from_dict(json.loads(path.read_text()))
        self.assertEqual(manifest.name, "portable-research-agent")
        self.assertIn("portable-json", manifest.runtimes)


if __name__ == "__main__":
    unittest.main()
