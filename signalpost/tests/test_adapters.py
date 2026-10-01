import json
import tempfile
import unittest
from pathlib import Path

from signalpost.adapters import BulkBrregAdapter, FixtureBrregAdapter, LiveBrregAdapter, LocalJsonlAdapter


FIXTURE = Path(__file__).parents[1] / "src" / "signalpost" / "fixtures" / "brreg_fixture.json"


class AdapterTests(unittest.TestCase):
    def test_fixture_is_offline_and_complete_for_known_company(self):
        adapter = FixtureBrregAdapter(FIXTURE)
        result = adapter.fetch_company("923609016")
        self.assertEqual(result["legal_identity"].body["organisasjonsnummer"], "923609016")
        self.assertEqual(result["annual_account_history"].body, ["2025", "2024"])
        self.assertEqual(result["legal_identity"].retrieved_at, "2026-09-01T00:00:00Z")

    def test_local_jsonl_matches_fixture_shape(self):
        record = {"organisation_number": "974760673", "modules": {"legal_identity": {"status_code": 200, "body": {"organisasjonsnummer": "974760673", "navn": "Local"}}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            result = LocalJsonlAdapter(path).fetch_company("974760673")
        self.assertEqual(result["legal_identity"].body["navn"], "Local")

    def test_live_adapter_isolated_behind_injected_opener(self):
        requested = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"{}"

        def opener(request, timeout):
            requested.append((request.full_url, timeout))
            return Response()

        result = LiveBrregAdapter(timeout_seconds=2, opener=opener).fetch_company("923609016")
        self.assertEqual(set(result), {"legal_identity", "leadership", "workplaces", "group_links", "annual_accounts", "annual_account_history"})
        self.assertEqual(len(requested), 6)
        self.assertTrue(all(url.startswith("https://data.brreg.no/") for url, _ in requested))
        self.assertTrue(all(timeout == 2 for _, timeout in requested))

    def test_bulk_csv_loader_anchors_identity_without_network(self):
        csv_text = "organisasjonsnummer;navn;organisasjonsform.kode;antallAnsatte;hjemmeside\n923609016;Example Signal AS;AS;3;https://example.no/\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entities.csv"
            path.write_text(csv_text, encoding="utf-8")
            result = BulkBrregAdapter(path).fetch_company("923609016")
        self.assertEqual(result["legal_identity"].body["navn"], "Example Signal AS")
        self.assertEqual(result["legal_identity"].source_class, "official_registry_bulk")


if __name__ == "__main__":
    unittest.main()
