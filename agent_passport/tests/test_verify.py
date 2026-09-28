import unittest

from agent_passport.demo import build_demo_core
from agent_passport.verify import run_checks


class VerificationTests(unittest.TestCase):
    def test_all_local_checks_pass(self) -> None:
        results = run_checks(build_demo_core())
        self.assertEqual([result.name for result in results], [
            "manifest-valid", "adapter-parity", "deterministic-replay", "invalid-input-rejected"
        ])
        self.assertTrue(all(result.passed for result in results), results)


if __name__ == "__main__":
    unittest.main()
