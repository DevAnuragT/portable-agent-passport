# Signalpost source policy

## Allowed sources

1. Brønnøysundregistrene Enhetsregisteret, roles, subunits, group and
   Regnskapsregisteret endpoints for official identity and filed data.
2. A website only when its URL is supplied by the official registry and the
   static response is limited to the same registered domain.
3. Static HTML, JSON-LD, metadata, links, and robots information obtained from
   that registry-listed site.

Search results are not evidence. LinkedIn, Meta, Glassdoor, Indeed, Google,
and similar restricted platforms are not scraped or used as sole evidence.

## Website controls

- HTTP(S) URLs only; credentials and arbitrary user-supplied URLs are rejected.
- Cross-registered-domain redirects abstain.
- `robots.txt` is checked before a registry-listed page is fetched.
- A `Disallow: /` rule for `*` or `Signalpost` blocks crawling.
- Responses are capped at 1 MiB and requests use a bounded budget.
- Website claims require exact organisation-number or legal-name corroboration.
- Every published claim points to an evidence span, retrieval time, and content hash.
