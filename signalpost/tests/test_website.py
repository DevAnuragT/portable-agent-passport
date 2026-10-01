import hashlib
import unittest

from signalpost.website import (
    FetchResponse,
    WebsiteEnricher,
    WebsiteFetcher,
    is_allowed_url,
    parse_static_html,
    same_registered_domain,
)


HTML = """
<!doctype html><html><head>
<title>Example Industries</title>
<meta name="description" content="Industrial systems and services">
<link rel="canonical" href="https://www.example.co.uk/">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Example Industries AS","identifier":"123 456 789","email":"hello@example.co.uk","address":{"@type":"PostalAddress","streetAddress":"1 Main Street","addressLocality":"London"}}</script>
</head><body><h1>Example Industries AS</h1>
<address>1 Main Street, London</address>
<a href="/careers">Careers</a><a href="https://jobs.example.co.uk/openings">Jobs</a>
<a href="/news/launch">News</a></body></html>
"""


class WebsiteTests(unittest.TestCase):
    def test_url_and_registered_domain_allowlist(self):
        self.assertTrue(is_allowed_url("https://example.co.uk/path"))
        self.assertTrue(is_allowed_url("http://example.co.uk"))
        self.assertFalse(is_allowed_url("javascript:alert(1)"))
        self.assertFalse(is_allowed_url("example.co.uk"))
        self.assertFalse(is_allowed_url("https://user:secret@example.co.uk"))
        self.assertTrue(same_registered_domain("https://www.example.co.uk", "https://jobs.example.co.uk"))
        self.assertFalse(same_registered_domain("https://example.co.uk", "https://example.com"))
        self.assertFalse(same_registered_domain("https://example.co.uk", "https://example.co.uk.evil.test"))
        self.assertFalse(is_allowed_url("http://127.0.0.1/"))
        self.assertFalse(is_allowed_url("http://localhost/"))
        self.assertFalse(is_allowed_url("http://192.168.1.10/"))

    def test_static_parser_extracts_identity_and_evidence_backed_claims(self):
        result = parse_static_html(HTML, "https://example.co.uk", "123456789", "Example Industries AS", "2026-09-30T12:00:00Z")
        self.assertTrue(result.identity_proven)
        self.assertFalse(result.abstained)
        self.assertEqual(result.canonical_url, "https://www.example.co.uk/")
        self.assertEqual(result.title, "Example Industries")
        self.assertEqual(result.description, "Industrial systems and services")
        fields = {claim.field for claim in result.claims}
        self.assertTrue({"organization", "canonical_url", "title", "description", "contact", "address", "careers_links", "jobs_links", "news_links"} <= fields)
        for claim in result.claims:
            self.assertEqual(claim.source_url, "https://example.co.uk/")
            self.assertEqual(claim.retrieved_at, "2026-09-30T12:00:00Z")
            self.assertEqual(claim.content_sha256, hashlib.sha256(HTML.encode()).hexdigest())
            self.assertTrue(claim.evidence_quote)
        self.assertEqual(result.claims, tuple(sorted(result.claims, key=lambda claim: (claim.field, claim.id))))
        self.assertEqual(result.claims, parse_static_html(HTML, "https://example.co.uk", "123456789", "Example Industries AS", "2026-09-30T12:00:00Z").claims)
        later = parse_static_html(HTML, "https://example.co.uk", "123456789", "Example Industries AS", "2026-10-01T12:00:00Z")
        self.assertEqual([claim.id for claim in result.claims], [claim.id for claim in later.claims])

    def test_unproven_identity_abstains_without_candidate_claims(self):
        result = parse_static_html("<html><title>Unrelated</title><body>Welcome</body></html>", "https://example.co.uk", "123456789", "Example Industries AS", "2026-09-30T12:00:00Z")
        self.assertTrue(result.abstained)
        self.assertFalse(result.identity_proven)
        self.assertEqual(result.claims, ())

    def test_matching_name_without_organisation_number_is_not_identity_proof(self):
        result = parse_static_html("<html><body>Example Industries AS</body></html>", "https://example.co.uk", "123456789", "Example Industries AS", "2026-09-30T12:00:00Z")
        self.assertTrue(result.abstained)
        self.assertEqual(result.claims, ())

    def test_legal_name_plus_registered_address_is_secondary_identity_proof(self):
        html = "<html><body><h1>Example Industries AS</h1><address>1 Main Street, London</address></body></html>"
        result = parse_static_html(html, "https://example.co.uk", "123456789", "Example Industries AS", "2026-09-30T12:00:00Z", {"streetAddress": "1 Main Street", "addressLocality": "London"})
        self.assertTrue(result.identity_proven)
        self.assertTrue(result.claims)

    def test_registry_listed_domain_plus_legal_name_is_secondary_identity_proof(self):
        html = "<html><title>Example Industries AS</title><body>Example Industries AS</body></html>"
        result = parse_static_html(html, "https://example.co.uk", "123456789", "Example Industries A/S", "2026-09-30T12:00:00Z", registry_domain_proof=True)
        self.assertTrue(result.identity_proven)

    def test_injected_fetcher_is_used_and_cross_domain_redirect_abstains(self):
        seen = []

        def fetch(url):
            seen.append(url)
            return FetchResponse(HTML.encode(), 200, "2026-09-30T12:00:00Z", "https://www.example.co.uk/")

        result = WebsiteEnricher(fetch).enrich("https://example.co.uk", "123456789", "Example Industries AS")
        self.assertEqual(seen, ["https://example.co.uk/"])
        self.assertTrue(result.identity_proven)

        redirected = WebsiteEnricher(lambda url: FetchResponse(HTML.encode(), 200, "2026-09-30T12:00:00Z", "https://other.test/")).enrich("https://example.co.uk", "123456789", "Example Industries AS")
        self.assertTrue(redirected.abstained)
        self.assertEqual(redirected.claims, ())

    def test_verified_sitemap_pages_emit_only_fetched_evidence(self):
        robots = b"User-agent: *\nAllow: /\nSitemap: https://example.co.uk/declared.xml\nDisallow: /private\n"
        sitemap = b"""<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
          <url><loc>https://example.co.uk/careers/engineer</loc><lastmod>2026-09-20</lastmod></url>
          <url><loc>https://example.co.uk/news/launch</loc></url>
          <url><loc>https://other.example.net/jobs/fake</loc></url>
        </urlset>"""
        homepage = b"<html><body>Example Industries AS 123 456 789</body></html>"
        job = b"""<html><body><script type='application/ld+json'>
          {\"@type\":\"JobPosting\",\"title\":\"Engineer\",\"datePosted\":\"2026-09-20\",\"url\":\"https://example.co.uk/careers/engineer\"}
        </script></body></html>"""
        news = b"""<html><body><script type='application/ld+json'>
          {\"@type\":\"NewsArticle\",\"headline\":\"Launch\",\"datePublished\":\"2026-09-21\",\"url\":\"https://example.co.uk/news/launch\"}
        </script></body></html>"""
        payloads = {
            "https://example.co.uk/robots.txt": robots,
            "https://example.co.uk/": homepage,
            "https://example.co.uk/declared.xml": sitemap,
            "https://example.co.uk/sitemap.xml": b"not xml",
            "https://example.co.uk/careers/engineer": job,
            "https://example.co.uk/news/launch": news,
        }
        requested = []

        class Response:
            def __init__(self, url, body):
                self.url, self.status, self._body = url, 200, body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit=None):
                return self._body

        def opener(request, timeout):
            requested.append(request.full_url)
            return Response(request.full_url, payloads[request.full_url])

        results = WebsiteFetcher(opener=opener, max_requests=10, max_pages=4).fetch(
            "123456789", {"website": "https://example.co.uk/", "name": "Example Industries AS"}
        )
        hiring = results["hiring_activity"].body
        activity = results["public_activity"].body
        self.assertEqual([item["source_url"] for item in hiring["jobs"]], ["https://example.co.uk/careers/engineer"])
        self.assertEqual([item["source_url"] for item in activity["news"]], ["https://example.co.uk/news/launch"])
        self.assertEqual(hiring["jobs"][0]["date"], "2026-09-20")
        self.assertEqual(activity["news"][0]["date"], "2026-09-21")
        self.assertTrue(hiring["jobs"][0]["content_sha256"])
        self.assertTrue(hiring["jobs"][0]["evidence_quote"])
        self.assertNotIn("https://example.co.uk/careers/engineer", hiring["careers"])
        discovered = results["website_sitemap"].body["candidate_pages"]
        self.assertTrue(all(item["discovery_only"] for item in discovered))
        self.assertIn("https://example.co.uk/declared.xml", requested)
        self.assertIn("https://example.co.uk/sitemap.xml", requested)
        self.assertLessEqual(len([url for url in requested if "/careers/" in url or "/news/" in url]), 4)

    def test_sitemap_waits_for_verified_homepage_and_does_not_publish_url(self):
        requested = []

        class Response:
            def __init__(self, url, body):
                self.url, self.status, self._body = url, 200, body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit=None):
                return self._body

        def opener(request, timeout):
            requested.append(request.full_url)
            body = b"User-agent: *\nAllow: /" if request.full_url.endswith("robots.txt") else b"<html><body>Unrelated</body></html>"
            return Response(request.full_url, body)

        results = WebsiteFetcher(opener=opener).fetch(
            "123456789", {"website": "https://example.co.uk/", "name": "Example Industries AS"}
        )
        self.assertNotIn("https://example.co.uk/sitemap.xml", requested)
        self.assertEqual(results["hiring_activity"].body["jobs"], [])
        self.assertEqual(results["public_activity"].body["news"], [])

    def test_robots_is_applied_to_each_discovered_page(self):
        robots = b"User-agent: *\nDisallow: /news\n"
        sitemap = b"<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://example.co.uk/news/hidden</loc></url></urlset>"
        homepage = b"<html><body>Example Industries AS 123 456 789</body></html>"
        requested = []

        class Response:
            status = 200
            def __init__(self, url, body):
                self.url, self._body = url, body
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit=None): return self._body

        def opener(request, timeout):
            requested.append(request.full_url)
            body = {"https://example.co.uk/robots.txt": robots, "https://example.co.uk/": homepage, "https://example.co.uk/sitemap.xml": sitemap}[request.full_url]
            return Response(request.full_url, body)

        results = WebsiteFetcher(opener=opener, max_requests=8).fetch(
            "123456789", {"website": "https://example.co.uk/", "name": "Example Industries AS"}
        )
        self.assertNotIn("https://example.co.uk/news/hidden", requested)
        self.assertEqual(results["public_activity"].body["news"], [])


if __name__ == "__main__":
    unittest.main()
