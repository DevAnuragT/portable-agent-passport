import unittest

from agent_passport.manifest import PassportManifest


class PassportManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = PassportManifest(
            name="research-agent",
            version="1.0.0",
            capabilities=("summarise", "cite"),
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            runtimes=("native", "adapter-a"),
        )

    def test_serialises_and_round_trips(self) -> None:
        restored = PassportManifest.from_dict(self.manifest.to_dict())
        self.assertEqual(restored, self.manifest)
        self.assertEqual(len(self.manifest.fingerprint()), 64)

    def test_rejects_duplicate_capabilities(self) -> None:
        invalid = PassportManifest(
            name="agent",
            version="1",
            capabilities=("search", "search"),
            input_schema={},
            output_schema={},
            runtimes=("native",),
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
