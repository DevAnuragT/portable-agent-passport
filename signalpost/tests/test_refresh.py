import copy
import unittest

from signalpost.refresh import refresh_claims, refresh_json


def claim(field, value, source="https://example.no"):
    return {"id": f"claim-{field}", "field": field, "value": value, "availability": "available", "source_url": source, "evidence_ids": [f"ev-{field}"]}


def evidence(field, quote):
    return {"id": f"ev-{field}", "source_url": "https://example.no", "retrieved_at": "2026-10-01T00:00:00Z", "content_hash": "a" * 64, "span": {"locator": "html", "quote": quote}}


class RefreshTests(unittest.TestCase):
    def test_new_changed_removed_and_history_preserved(self):
        previous = [claim("name", "Old AS"), claim("employees", 2)]
        current = [claim("name", "New AS"), claim("website", "https://example.no")]
        result = refresh_claims(previous, [evidence("name", "Old AS"), evidence("employees", "2")], current, [evidence("name", "New AS"), evidence("website", "example.no")])
        self.assertEqual({item["field"] for item in result.claims}, {"name", "website"})
        self.assertEqual({item["change_type"] for item in result.changes}, {"changed_value", "new_claim", "claim_removed"})
        self.assertEqual(len(result.evidence), 4)

    def test_failed_refresh_retains_supported_values_and_emits_no_removal(self):
        previous = [claim("name", "Stable AS")]
        result = refresh_claims(previous, [evidence("name", "Stable AS")], [], [], refresh_state="failed")
        self.assertEqual(result.claims[0]["value"], "Stable AS")
        self.assertEqual(result.changes, ())
        self.assertTrue(result.retained_after_failure)

    def test_replay_is_deterministic_and_inputs_unchanged(self):
        previous = {"claims": [claim("name", "Old")], "evidence": [evidence("name", "Old")]}
        current = {"claims": [claim("name", "New")], "evidence": [evidence("name", "New")]}
        before = copy.deepcopy((previous, current))
        first = refresh_json(previous, current)
        second = refresh_json(previous, current)
        self.assertEqual(first, second)
        self.assertEqual((previous, current), before)


if __name__ == "__main__":
    unittest.main()
