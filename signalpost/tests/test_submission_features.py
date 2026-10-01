import json
import tempfile
import unittest
from pathlib import Path

from signalpost.adapters import FixtureBrregAdapter, ModuleResult
from signalpost.batch import read_output_jsonl, run_batch
from signalpost.models import CompanyInput
from signalpost.smoke import build_report, generated_inputs
from signalpost.website import WebsiteFetcher, parse_company_html


FIXTURE = Path(__file__).parents[1] / "src" / "signalpost" / "fixtures" / "brreg_fixture.json"


class _Response:
    def __init__(self, url, body, status=200):
        self.url = url
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=None):
        return self._body


class _BaseAdapter:
    revision = "website-test"
    reference_time = "2026-09-01T00:00:00Z"
    deterministic = True

    def fetch_company(self, org):
        return {"legal_identity": ModuleResult("legal_identity", "https://data.brreg.no/enhetsregisteret/api/enheter/" + org, self.reference_time, 200, {"organisasjonsnummer": org, "navn": "Example Signal AS", "hjemmeside": "https://example.no/"}, content_sha256="a" * 64)}


class SubmissionFeatureTests(unittest.TestCase):
    def test_html_parser_requires_exact_identity_evidence_and_finds_jsonld_job(self):
        html = """<html><head><title>Example Signal AS</title><meta name='description' content='Builds tools'><script type='application/ld+json'>{\"@type\":\"JobPosting\",\"title\":\"Engineer\",\"datePosted\":\"2026-08-01\",\"url\":\"https://example.no/jobs/engineer\"}</script></head><body><p>Example Signal AS, 923 609 016</p></body></html>"""
        parsed = parse_company_html(html, "https://example.no/", "923609016", "Example Signal AS")
        self.assertTrue(parsed["verified"])
        self.assertIn("https://example.no/jobs/engineer", parsed["links"]["jobs"])
        self.assertFalse(any(claim["field"] == "contact" for claim in parsed["candidate_claims"]))
        wrong = parse_company_html(html, "https://example.no/", "974760673", "Other AS")
        self.assertFalse(wrong["verified"])

    def test_website_fetcher_checks_robots_and_stays_on_same_host(self):
        html = b"<html><title>Example Signal AS</title><body>Example Signal AS 923 609 016</body></html>"

        def opener(request, timeout):
            if request.full_url.endswith("robots.txt"):
                return _Response(request.full_url, b"User-agent: *\nAllow: /\n")
            return _Response(request.full_url, html)

        results = WebsiteFetcher(opener=opener, max_requests=3).fetch("923609016", {"website": "https://example.no/", "name": "Example Signal AS"})
        self.assertTrue(results["website_profile"].body["verified"])
        self.assertEqual(results["website_profile"].source_class, "company_owned")

    def test_website_fetcher_honours_robots_disallow(self):
        requested = []

        def opener(request, timeout):
            requested.append(request.full_url)
            return _Response(request.full_url, b"User-agent: *\nDisallow: /\n")

        results = WebsiteFetcher(opener=opener).fetch("923609016", {"website": "https://example.no/", "name": "Example Signal AS"})
        self.assertEqual(results["website_profile"].status_code, 403)
        self.assertEqual(requested, ["https://example.no/robots.txt"])

    def test_refresh_diff_and_resume_without_refetch(self):
        class CountingAdapter(FixtureBrregAdapter):
            calls = 0

            def fetch_company(self, organisation_number):
                self.calls += 1
                return super().fetch_company(organisation_number)

        inputs = [CompanyInput("923609016")]
        first_adapter = CountingAdapter(FIXTURE)
        first = run_batch(inputs, first_adapter)
        prior = {first[0].organisation_number: first[0].to_dict()}
        prior[first[0].organisation_number]["claims"][0]["value"]["name"] = "Previous Name"
        second_adapter = CountingAdapter(FIXTURE)
        refreshed = run_batch(inputs, second_adapter, previous=prior)
        self.assertTrue(any(change.change_type == "changed_value" for change in refreshed[0].changes))
        resumed_adapter = CountingAdapter(FIXTURE)
        resumed = run_batch(inputs, resumed_adapter, previous=prior, resume=True)
        self.assertEqual(resumed_adapter.calls, 0)
        self.assertEqual(resumed[0].organisation_number, "923609016")

    def test_smoke_report_has_100_terminal_envelopes(self):
        inputs = generated_inputs(100)
        envelopes = run_batch(inputs, FixtureBrregAdapter(FIXTURE))
        report = build_report(envelopes, 100, "test")
        self.assertTrue(report["exactly_one_terminal_envelope_per_input"])
        self.assertEqual(report["terminal_envelopes"], 100)
        self.assertTrue(report["checks_passed"])

    def test_output_round_trip_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.jsonl"
            run_batch([CompanyInput("923609016")], FixtureBrregAdapter(FIXTURE), path)
            records = read_output_jsonl(path)
        self.assertIn("923609016", records)


if __name__ == "__main__":
    unittest.main()
