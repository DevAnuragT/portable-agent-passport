# Local results

`offline-smoke-100.json` is **not** an official score or a real-company coverage test.
It runs 2 saved fixture companies plus 98 generated valid organisation numbers
absent from the fixture, to verify one terminal envelope per input.

Result: 100/100 terminal envelopes; 2 `available`, 98 `not_available`;
zero reported wrong-company publications; zero external requests; $0 API cost.

Before submission: run the agent on 100 companies from Builderr's public
universe with permitted live sources, audit source spans, test refresh/replay,
measure real request/runtime/cost budgets, and save that report separately.

One-company live BRREG probe on 1 October 2026: one available envelope,
six requests, 6,896 ms, $0 third-party cost; `live-probe-eval.json` passed
local schema checks. Input/output raw data were removed after inspection.
This is not a coverage, provenance-authenticity, or official-score test.

Public-universe 10 probe: `public-universe-10-eval.json` passed. It used the
first 10 public-universe companies, BRREG-only, with 10/10 exact identities,
50 available claims, 60 evidence links, 0 unsupported claims, 60 requests,
65,767 ms sequential runtime, and $0 third-party cost. It is a precision and
contract test, not a qualification score. Sequential extrapolation is too slow
for 1,000 companies; concurrency and budget controls were added next.

Official-sized identity run: `public-universe-1000-eval.json` passed. First
1,000 public-universe companies, BRREG `legal_identity` only, 16 workers,
global request budget 1,000: 1,000/1,000 envelopes and exact identities,
1,000 requests, p50 854 ms, p95 1,142 ms, $0. Not a full profile or
competition score. Full 411,160-company live crawling is neither required nor
appropriate; Builderr supplies a hidden official batch.

Website loop: `public-universe-100-website-eval.json` passed. BRREG identity
plus registry-listed static websites, 16 workers, 200-request cap: 100/100
envelopes, 135 requests, 18 website candidates, 4 identity-verified websites,
0 unsupported claims, 0 errors, $0. Unverified sites were abstained from.

Corrected discovery report: `public-universe-100-discovery-v2-eval.json` passes
with 100/100 envelopes, 146 requests, 4 verified official websites, 0 jobs,
0 public-activity claims, 0 errors, and $0. Website URLs are canonical or
explicitly derived from verified fetch URLs; titles/descriptions are not URLs.

Foundation report: `public-universe-100-foundation-v2-eval.json` has 100/100
envelopes, 646 requests, 100 identities, 100 annual accounts, 99 account
histories, 98 leadership, 100 workplaces, 15 group links, and one transient
429 handled as source-blocked. Not an official score.

RSS experiment: `news-rss-next-100-report.json` queried a zero-overlap slice
(rows 101–200). 90 companies had usable identities; 90 exact-title Google News
RSS queries returned 0 accepted mentions and 0 request errors. Results remain
discovery-only and are not published/evaluable evidence. No-key RSS is not worth
further budget without better discovery or rights-approved access.
