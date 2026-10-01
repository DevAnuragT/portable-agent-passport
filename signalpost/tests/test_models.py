import unittest

from signalpost.models import Availability, Claim, Evidence, EvidenceSpan, ValidationError, content_hash


class ModelTests(unittest.TestCase):
    def test_available_claim_requires_evidence(self):
        with self.assertRaises(ValidationError):
            Claim("c", "name", "Example", Availability.AVAILABLE)

    def test_missing_value_cannot_be_encoded_as_zero(self):
        with self.assertRaises(ValidationError):
            Claim("c", "employees", 0, Availability.NOT_AVAILABLE)

    def test_evidence_has_hash_and_span(self):
        body = {"name": "Example"}
        item = Evidence(
            "e1", "https://example.no/", "fixture", "official_registry",
            "2026-09-01T00:00:00Z", content_hash(body), EvidenceSpan("/name", "Example"),
        )
        self.assertEqual(len(item.content_hash), 64)
        self.assertEqual(item.to_dict()["span"]["locator"], "/name")


if __name__ == "__main__":
    unittest.main()
