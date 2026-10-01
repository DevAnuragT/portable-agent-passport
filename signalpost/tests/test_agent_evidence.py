import unittest

from signalpost.adapters import ModuleResult
from signalpost.agent import SignalpostAgent
from signalpost.models import Availability, CompanyInput, content_hash
from signalpost.website import parse_static_html


ORG = "923609016"
TIMESTAMP = "2026-09-30T12:00:00Z"
REGISTRY_URL = f"https://data.brreg.no/enhetsregisteret/api/enheter/{ORG}"
WEBSITE_URL = "https://example.no/"


class _VerifiedEmptyWebsiteAdapter:
    revision = "verified-empty-website"
    reference_time = TIMESTAMP
    deterministic = True
    last_request_count = 0

    def fetch_company(self, organisation_number):
        identity_body = {
            "organisasjonsnummer": organisation_number,
            "navn": "Example Signal AS",
            "hjemmeside": WEBSITE_URL,
        }
        html = b"<html><head><title>Example Signal AS</title></head><body>Example Signal AS 923 609 016</body></html>"
        parsed = parse_static_html(html, WEBSITE_URL, organisation_number, "Example Signal AS", TIMESTAMP)
        website_body = parsed.to_dict()
        return {
            "legal_identity": ModuleResult("legal_identity", REGISTRY_URL, TIMESTAMP, 200, identity_body, content_sha256=content_hash(identity_body)),
            "website_profile": ModuleResult("website_profile", WEBSITE_URL, TIMESTAMP, 200, website_body, content_sha256=parsed.content_sha256, source_class="company_owned"),
            "hiring_activity": ModuleResult("hiring_activity", WEBSITE_URL, TIMESTAMP, 200, {"jobs": [], "careers": []}, content_sha256=parsed.content_sha256, source_class="company_owned"),
            "public_activity": ModuleResult("public_activity", WEBSITE_URL, TIMESTAMP, 200, {"news": []}, content_sha256=parsed.content_sha256, source_class="company_owned"),
        }


class AgentEvidenceTests(unittest.TestCase):
    def test_verified_empty_website_observations_are_not_available(self):
        envelope = SignalpostAgent(_VerifiedEmptyWebsiteAdapter()).research(CompanyInput(ORG))
        by_field = {claim.field: claim for claim in envelope.claims}

        self.assertEqual(by_field["legal_identity"].availability, Availability.AVAILABLE)
        self.assertEqual(by_field["official_website"].availability, Availability.AVAILABLE)
        self.assertEqual(by_field["hiring_activity"].availability, Availability.NOT_AVAILABLE)
        self.assertEqual(by_field["public_activity"].availability, Availability.NOT_AVAILABLE)
        self.assertIsNone(by_field["hiring_activity"].value)
        self.assertIsNone(by_field["public_activity"].value)

    def test_normalised_identity_is_marked_derived_and_keeps_raw_hash(self):
        envelope = SignalpostAgent(_VerifiedEmptyWebsiteAdapter()).research(CompanyInput(ORG))
        identity_claim = next(claim for claim in envelope.claims if claim.field == "legal_identity")
        evidence = next(item for item in envelope.evidence if item.id == identity_claim.evidence_ids[0])
        identity_body = _VerifiedEmptyWebsiteAdapter().fetch_company(ORG)["legal_identity"].body

        self.assertEqual(evidence.content_hash, content_hash(identity_body))
        self.assertEqual(evidence.extraction_method, "derived_json_normalization")
        self.assertEqual(evidence.span.kind, "derived")
        self.assertIn("not a verbatim source quote", evidence.span.quote)
        self.assertEqual(identity_claim.value["organisation_number"], ORG)

    def test_expected_not_found_modules_are_not_run_errors(self):
        adapter = _VerifiedEmptyWebsiteAdapter()
        original = adapter.fetch_company

        def fetch(org):
            result = original(org)
            result["group_links"] = ModuleResult("group_links", "https://data.brreg.no/group", TIMESTAMP, 404, None, "source returned HTTP error: 404", content_hash(None))
            return result

        adapter.fetch_company = fetch
        envelope = SignalpostAgent(adapter).research(CompanyInput(ORG))
        self.assertFalse(any(error.module == "group_links" for error in envelope.errors))

    def test_page_title_cannot_be_published_as_official_website(self):
        class Adapter(_VerifiedEmptyWebsiteAdapter):
            def fetch_company(self, organisation_number):
                result = super().fetch_company(organisation_number)
                parsed = parse_static_html(
                    b"<html><head><title>Example Signal</title></head><body>Example Signal AS 923 609 016</body></html>",
                    WEBSITE_URL,
                    organisation_number,
                    "Example Signal AS",
                    TIMESTAMP,
                )
                result["website_profile"] = ModuleResult("website_profile", WEBSITE_URL, TIMESTAMP, 200, parsed.to_dict(), content_sha256=parsed.content_sha256, source_class="company_owned")
                return result

        envelope = SignalpostAgent(Adapter()).research(CompanyInput(ORG))
        website = next(claim for claim in envelope.claims if claim.field == "official_website")
        self.assertNotEqual(website.value, "Example Signal")


if __name__ == "__main__":
    unittest.main()
