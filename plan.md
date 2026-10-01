# Signalpost Implementation Plan

## Goal

Ship reproducible Signalpost agent for Builderr:

```text
organisation number batch -> exact identity -> permitted sources -> evidence-backed profile
```

Success conditions:

- one terminal envelope per input company;
- zero unsupported or wrong-company publications in regression fixtures;
- deterministic, resumable batch execution;
- source URL, retrieval time, reporting period, content hash, and evidence span per claim;
- refresh preserves history and emits material changes;
- clean-install command works;
- 100-company smoke report produced;
- local tests pass before submission.

## Product boundary

LLM is optional. Deterministic registry, website, structured-data, HTML, and PDF extraction stay on the critical path. Add bounded LLM extraction only after measured coverage gaps justify it. Never let an LLM override identity or evidence gates.

Preferred sources:

1. Brønnøysundregistrene identity, roles, subunits, and annual accounts.
2. Registry-linked company website, sitemap, JSON-LD, careers, news, and contact pages.
3. Official/licensed/permitted external sources only.

## Loop protocol

After every feature:

1. Update `tasks.md` with what changed and test result.
2. Run focused tests plus relevant smoke test.
3. Record failures, coverage gaps, request count, runtime, and evidence problems.
4. Re-plan the next smallest high-value feature here and in `tasks.md`.
5. Implement only after the next task is explicit.
6. Repeat until all release gates pass.

## Current checkpoint (1 October 2026)

The deterministic baseline is implemented and locally verified. The latest
100-company public-universe foundation output passes the local evaluator:
100/100 terminal envelopes, 100/100 exact identities, 534 available claims,
534 linked evidence spans with 100% span validity, zero unsupported claims,
646 requests, p95 runtime 43,459 ms per company, and $0 third-party cost. It
contains 33 `failed` claims and 347 `not_available` claims; these states and the
single transient BRREG 429 must remain visible. This is a local public-universe
run, not an official Builderr score.

The 100-company website discovery run is much sparser: 4 identity-verified
websites, no accepted hiring or public-activity claims, zero unsupported claims,
and 146 requests. The separate rows 101–200 Google News RSS experiment yielded
no accepted mentions and should not be repeated without a permitted, higher-yield
discovery source. The 1,000-company run is identity-only and must not be
represented as full enrichment.

The documented 100-input synthetic smoke passes: 100/100 envelopes, two fixture
companies and 98 deliberate `not_available` results. The 37 Signalpost unit
tests and four evaluator tests pass when run with `PYTHONPATH=signalpost/src`.
The standalone evaluator is a contract/evidence check, not a competition scorer.

Next: freeze a reproducible baseline commit and submit it to Builderr for an
official run. Do not claim qualification until Builderr returns an official
score. Use that score to select a permitted discovery improvement; prioritize
coverage while preserving exact-company and evidence gates. Current local
results cannot predict the 65/100 threshold because synthesis/UX and official
recall are not evaluated locally.

One-company BRREG live probe: 6 requests, ~6.9 seconds, available official
identity/accounts/roles/workplaces/group; local schema evaluator passed. This
does not measure real coverage or source-span authenticity. At 1,000 companies,
six requests each would exceed the 2,000-request limit in the initial Unstop
description. Confirm the currently enforced limit with Builderr, then batch or
prioritize official endpoints before scale testing.

Fresh public-universe test: first 10 eligible companies, BRREG-only, no website:
10/10 envelopes, 100% identity precision, 50 supported claims, 60 evidence
links, 0 unsupported claims, 60 requests, 65,767 ms sequential runtime, $0
third-party cost. Extrapolation is ~600 requests and ~11 minutes for 100, and
~6,000 requests and ~110 minutes for 1,000. This proves correctness on 10, not
official qualification. Add bounded concurrency and a request budget before the
1,000-company run.

Official-sized local identity run completed on first 1,000 public-universe org.nr:
BRREG `legal_identity` only, 16 workers, global request budget 1,000. Result:
1,000/1,000 terminal envelopes, 1,000/1,000 exact identities, zero schema or
unsupported-claim findings, 1,000 requests, $0 third-party cost, per-company
p50 854 ms and p95 1,142 ms. It produced 1,141 available claims and 6,141
evidence links; 8,000 fields stayed honestly `not_available` because other
modules were not requested. This validates batch execution/identity precision,
not competition score.

Do not live-crawl all 411,160 public companies. Builderr supplies only its hidden
official batch; public universe is local development data. Full enrichment for
1,000 companies needs budgeted module selection and website crawl measurement.

100-company website loop completed: identity-only BRREG + registry-listed static
website fetch, 16 workers, 200-request cap. Result: 100/100 envelopes, 135
requests, 18 registry website candidates, 4 websites identity-verified and
published, zero unsupported claims, zero run errors, $0 third-party cost. Most
registry domains did not prove identity in page content; those stayed withheld.
This is correct abstention, but recall needs a measured permitted discovery path.

Sitemap/evidence loop completed: corrected report passes with 100/100 envelopes,
146 requests, 4 verified official websites, zero job/news claims, zero errors,
and $0 third-party cost. Official URL claims now use canonical URLs or explicit
derived verified-fetch evidence; page titles/descriptions cannot masquerade as
URLs. Full foundation run passes with 100 identities, 100 annual accounts, 100
account histories, 98 leadership, 100 workplaces, and 15 group-link results;
one transient 429 was handled as blocked source data.

No-key external experiment completed on zero-overlap public-universe rows
101–200. BRREG identity resolved 90/100 rows; Google News RSS exact-title
connector queried 90 companies with four bounded workers, 0 request errors,
0 accepted mentions, and 0 companies with mentions. Output is discovery-only
and not publishable. This path adds no measured recall on this slice, so do not
spend more budget on it without a better candidate strategy or rights-approved
search provider. Next: submit the conservative foundation version for an
official baseline; select any subsequent coverage work from the official score.

Current Builderr board (1 October): 17 assessed, 0 qualified, locked 1,200-
company set. Published breakdown shows recall/coverage is the main loss area;
precision/evidence is comparatively high. Therefore next scoring work targets
permitted website, jobs, public activity, and other external evidence only after
identity gates pass.

Stop/replan when a connector violates source terms, identity accuracy falls, a
claim cannot be traced to raw bytes, or the run exceeds time/request/cost budget.

## Phases

### Phase 0 — Contract and skeleton

- Define JSONL input/output and terminal states.
- Create clean-install command.
- Add typed models and fixture tests.

### Phase 1 — Official foundation

- Validate Norwegian organisation numbers.
- Load BRREG bulk/API identity.
- Fetch roles, subunits, workplaces, group links, and annual accounts.
- Emit evidence-backed profiles.

### Phase 2 — Website enrichment

- Verify registry-listed domains.
- Fetch robots/sitemap/static HTML.
- Parse JSON-LD, OpenGraph, metadata, contact, leadership, locations, careers, jobs, and news.
- Add browser fallback only for confirmed JavaScript shells.

### Phase 3 — Safety and refresh

- Exact-company identity graph.
- Immutable snapshots and content hashes.
- Claim conflict handling.
- Idempotent refresh and typed change events.
- Explicit blocked/ambiguous/not-available outcomes.

### Phase 4 — Evaluation loop

- 100-company smoke run.
- 1,000-company local run when resources allow.
- Field coverage, evidence validity, identity precision, runtime, request, and cost reports.
- Zero-overlap regression fixtures.

### Phase 5 — Optional intelligence

- Add permitted search/news/jobs connectors.
- Measure each connector on development and validation sets.
- Add Gemini/Groq LLM fallback only for pages deterministic extraction cannot cover.
- Promote only with no wrong-company regression and measurable coverage gain.

### Phase 6 — Submission release

- Pin dependencies.
- Run from clean environment.
- Freeze code, prompts, models, policies, and thresholds.
- Produce smoke report.
- Submit exact commit to `submit@builderr.ai`.

## Release gates

- `pytest` passes.
- Every input gets exactly one terminal envelope.
- Required fields and allowed states validate.
- Wrong-company fixture count: zero.
- Material unsupported-claim fixture count: zero.
- Refresh replay is idempotent.
- Resume makes no duplicate requests.
- Clean-install command succeeds.
- Smoke report includes runtime, requests, cost, and failures.

## Official references

- Challenge: https://builderr.ai/challenges/signalpost
- Starter: https://builderr.ai/signalpost-starter-kit.tar.gz
- Brief: https://builderr.ai/starter-briefs/signalpost.md
- Playbook: https://builderr.ai/starter-briefs/signalpost-agent-playbook.md
- Evaluation contract: https://builderr.ai/docs/signalpost-evaluation-harness.md
