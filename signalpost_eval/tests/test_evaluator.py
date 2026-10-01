import json
import tempfile
import unittest
from pathlib import Path

from signalpost_eval.evaluator import evaluate_batch, evaluate_files


ROOT = Path(__file__).parents[1]


def _valid_envelope():
    digest = "a" * 64
    claims = [
        {"id": "c-identity", "field": "legal_identity", "value": {"organisation_number": "923609016", "name": "Fixture Company"}, "availability": "available", "confidence": 1.0, "evidence_ids": ["e-identity"]},
        {"id": "c-accounts", "field": "annual_accounts", "value": None, "availability": "not_available", "confidence": None, "evidence_ids": []},
        {"id": "c-leadership", "field": "leadership", "value": None, "availability": "not_available", "confidence": None, "evidence_ids": []},
        {"id": "c-workplaces", "field": "workplaces", "value": None, "availability": "not_available", "confidence": None, "evidence_ids": []},
        {"id": "c-group", "field": "group_links", "value": None, "availability": "not_available", "confidence": None, "evidence_ids": []},
        {"id": "c-website", "field": "official_website", "value": None, "availability": "not_available", "confidence": None, "evidence_ids": []},
        {"id": "c-activity", "field": "hiring_and_activity", "value": None, "availability": "not_available", "confidence": None, "evidence_ids": []},
    ]
    sections = {}
    for claim in claims:
        sections[claim["field"]] = {"availability": claim["availability"], "claim_ids": [claim["id"]]}
    return {
        "organisation_number": "923609016",
        "state": "available",
        "run": {"run_id": "run-1", "started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T00:00:00Z", "terminal_status": "available"},
        "profile": sections,
        "claims": claims,
        "evidence": [{"id": "e-identity", "source_url": "https://example.test/identity", "source_name": "fixture", "source_class": "official_registry", "retrieved_at": "2026-01-01T00:00:00Z", "content_hash": digest, "span": {"kind": "json_pointer", "locator": "/", "quote": '{"name":"Fixture Company","organisation_number":"923609016"}'}, "snapshot_id": "s-1"}],
        "snapshots": [{"id": "s-1", "source_url": "https://example.test/identity", "retrieved_at": "2026-01-01T00:00:00Z", "content_hash": digest, "status_code": 200, "source_class": "official_registry", "error": None}],
        "changes": [],
        "errors": [],
        "operations": {"requests": 1, "runtime_ms": 7, "third_party_cost_usd": 0.0},
    }


class EvaluatorTests(unittest.TestCase):
    def test_valid_contract_has_all_summary_sections(self):
        report = evaluate_batch([{"organisation_number": "923 609 016"}], [_valid_envelope()])
        self.assertTrue(report["passed"], report["findings"])
        self.assertEqual(report["schema"]["one_envelope_per_input"], True)
        self.assertEqual(report["identity"]["matching_count"], 1)
        self.assertEqual(report["evidence"]["unsupported_claim_count"], 0)
        self.assertEqual(report["requests"]["total_requests"], 1)
        self.assertEqual(report["runtime"]["runtime_ms"]["median"], 7.0)
        for key in ("schema", "identity", "evidence", "availability", "refresh", "requests", "runtime"):
            self.assertIn(key, report)

    def test_exactly_one_envelope_per_input_is_enforced(self):
        report = evaluate_batch([{"organisation_number": "923609016"}, {"organisation_number": "974760673"}], [_valid_envelope()])
        self.assertFalse(report["passed"])
        self.assertEqual(report["schema"]["missing_envelope_count"], 1)
        self.assertFalse(report["schema"]["one_envelope_per_input"])
        self.assertIn("missing_envelope", {item["code"] for item in report["findings"]})

    def test_regression_fixtures_catch_wrong_company_and_unsupported_claim(self):
        wrong = evaluate_files(ROOT / "fixtures/wrong_company/input.jsonl", ROOT / "fixtures/wrong_company/output.jsonl")
        unsupported = evaluate_files(ROOT / "fixtures/unsupported_claim/input.jsonl", ROOT / "fixtures/unsupported_claim/output.jsonl")
        self.assertFalse(wrong["passed"])
        self.assertEqual(wrong["identity"]["mismatch_count"], 1)
        self.assertIn("identity_claim_mismatch", {item["code"] for item in wrong["findings"]})
        self.assertFalse(unsupported["passed"])
        self.assertEqual(unsupported["evidence"]["unsupported_claim_count"], 1)
        self.assertIn("unsupported_claim", {item["code"] for item in unsupported["findings"]})

    def test_file_report_is_deterministic_and_json_serializable(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.jsonl"
            output_path = Path(directory) / "output.jsonl"
            input_path.write_text(json.dumps({"organisation_number": "923609016"}) + "\n", encoding="utf-8")
            output_path.write_text(json.dumps(_valid_envelope(), sort_keys=True) + "\n", encoding="utf-8")
            first = evaluate_files(input_path, output_path)
            second = evaluate_files(input_path, output_path)
        self.assertEqual(first, second)
        json.dumps(first, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
