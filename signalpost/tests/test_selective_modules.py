import unittest

from signalpost.adapters import FixtureBrregAdapter
from signalpost.agent import SignalpostAgent
from signalpost.models import CompanyInput
from signalpost.website import WebsiteFetcher


class SelectiveModuleTests(unittest.TestCase):
    def test_unrequested_modules_do_not_create_source_errors(self):
        adapter = FixtureBrregAdapter("signalpost/src/signalpost/fixtures/brreg_fixture.json")
        envelope = SignalpostAgent(adapter).research(CompanyInput("923609016"))
        self.assertFalse(any(error.code == "module_source_error" and error.module in {"annual_accounts", "leadership", "workplaces", "group_links"} for error in envelope.errors))

    def test_registry_host_without_scheme_is_accepted(self):
        calls = []

        class Response:
            def __init__(self, url, body):
                self.status = 200
                self.url = url
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit=None):
                return self._body

        def opener(request, timeout):
            calls.append(request.full_url)
            body = b"User-agent: *\nAllow: /" if request.full_url.endswith("robots.txt") else b"<html><body>Example Signal AS 923 609 016</body></html>"
            return Response(request.full_url, body)

        results = WebsiteFetcher(opener=opener).fetch("923609016", {"website": "example.no", "name": "Example Signal AS"})
        self.assertEqual(results["website_profile"].status_code, 200)
        self.assertTrue(results["website_profile"].body["verified"])
        self.assertEqual(calls[0], "https://example.no/robots.txt")


if __name__ == "__main__":
    unittest.main()
