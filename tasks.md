# Signalpost Tasks

Status values: `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`.

## Current loop

- Current feature: Phase 6 — freeze and submit conservative baseline
- Status: `IN_PROGRESS`; implementation and local contract checks pass, but no official Builderr score exists
- Latest verification: 37 Signalpost tests + 4 evaluator tests pass with `PYTHONPATH=signalpost/src`; latest public 100-company foundation output re-evaluates with 100/100 envelopes, exact identities, 534/534 available claims linked to valid evidence spans, zero unsupported claims, 646 requests, and p95 43.459 s/company. Synthetic smoke: 100/100 envelopes, 2 fixture-backed and 98 `not_available`; not a coverage or score test.
- Clean install was recorded as passing in the earlier local run. It was not repeated in this turn because the available host is Python 3.14.7 while the package explicitly supports Python 3.9–3.12; verify again on a declared runtime before sending the final packet.
- Coverage gap: website run found 4 verified sites and no hiring/public-activity claims; rows 101–200 RSS experiment found zero accepted mentions. Do not repeat RSS without a better permitted discovery source.
- Next: clean-install check, freeze the exact code/docs/reports commit, and submit repository URL, commit, one run command, 100-company report, source/model/licence/cost disclosures, and contact to Builderr. Await official score before choosing coverage work.

## Backlog

### Phase 0 — Contract and skeleton

- [x] P0.1 Create `signalpost/` package and pinned Python setup.
- [x] P0.2 Define input JSONL and terminal output envelope.
- [x] P0.3 Add typed models and validation tests.
- [x] P0.4 Add one-command local execution.

### Phase 1 — Official foundation

- [x] P1.1 Organisation-number validation.
- [x] P1.2 BRREG identity loader/API adapter.
- [x] P1.3 Roles, subunits, workplaces, group, and annual-account adapters.
- [x] P1.4 Claim/evidence persistence.

### Phase 2 — Website enrichment

- [x] P2.1 Registry-domain verification.
- [x] P2.2 robots/sitemap/static HTML crawler.
- [x] P2.3 JSON-LD/OpenGraph/HTML extraction.
- [x] P2.4 Careers/jobs/news extraction.
- [ ] P2.5 JavaScript fallback (defer until static coverage is measured).

### Phase 3 — Safety and refresh

- [x] P3.1 Exact-company identity gates.
- [x] P3.2 Immutable snapshots and hashes.
- [x] P3.3 Conflict resolution and abstention.
- [x] P3.4 Idempotent refresh/change events.

### Phase 4 — Evaluation

- [x] P4.1 100-company offline contract smoke runner (not live coverage).
- [x] P4.2 Local schema/identity/evidence report generator (not official scorer).
- [x] P4.3 Wrong-company/evidence regression suite.
- [x] P4.4 1,000-company identity-only scale run; full enrichment still pending.
- [x] P4.5 100-company live public-universe smoke reports with evidence audits; external coverage still pending.
- [ ] P4.6 Confirm the official evaluator's current request/time budget and tune the 100-company foundation path: observed p95 43.459 s/company; extrapolation is not a guarantee of completion.
- [x] P4.7 Bounded concurrent batch execution with stable output order and accurate per-company metrics.

### Phase 5 — Optional intelligence

- [ ] P5.1 Permitted search/news/jobs connectors.
- [ ] P5.2 Connector development/validation measurement.
- [ ] P5.3 Optional bounded LLM adapter.

### Phase 6 — Release

- [x] P6.1 Clean-machine install test.
- [x] P6.2 Offline final contract smoke report; live coverage report still required.
- [ ] P6.3 Freeze exact commit and submission package.
- [ ] P6.4 Submit to Builderr and record result.

## Loop log

| Iteration | Feature | Result | Next decision |
|---:|---|---|---|
| 0 | Plan + task contract | In progress | Build Phase 0 skeleton |
| 1 | Phase 0/1 core + evaluator | 15 tests passed; offline report passed; identity precision 66.67% on fixture because one input is intentionally absent | Build deterministic website parser and refresh layer; do not treat local schema pass as official score |
| 2 | Website + refresh | 29 tests passed; identity-gated static extraction; failed refresh retains old claims; evidence collision preserves both versions | Integrate website claims into agent envelope; then rerun smoke/evaluator |
| 3 | Safety tightening + offline 100 | 30 tests passed; exact org number required for website identity; 100 envelopes, 2 fixture-covered, 98 absent; no official score | Audit real source spans; integrate refresh/website into envelopes; run live 100-company test |
| 4 | One-company live probe | 1/1 BRREG envelope; 6 requests; ~6.9s; local schema evaluator passed; raw response not retained | Verify budget and real evidence support before scaled live run |
| 5 | MVP release verification | 26 core tests + 4 evaluator tests; clean venv install; offline 100 report; no LLM/API key | MVP ready; do not claim qualification until live 100 and official Builderr run |
| 6 | Public-universe 10 probe | BRREG-only: 10/10 envelopes, 100% identity precision, 50 available claims, 60 evidence links, 0 unsupported, 60 requests, 65.8s sequential, $0 | Add bounded concurrency and budget; then live 100 with website |
| 7 | Official-sized identity run | 1,000/1,000 envelopes; 100% identity; 0 validation findings; 1,000 requests; p50 854ms/p95 1,142ms; $0; identity-only | Run live 100 enrichment; full 411k live crawl is out of scope and unsafe |
| 8 | Website identity loop | 100/100 envelopes; 135 requests; 18 registry domains; 4 identity-verified websites; 0 unsupported claims/errors; $0 | Audit raw spans; add verified-domain sitemap/page discovery; evaluate permitted external discovery |
| 9 | Sitemap/evidence correction + foundation | 37 core + 4 evaluator tests; discovery 100/100, 146 requests, 4 verified sites, 0 errors; foundation 100 identities/accounts/histories/workplaces, 98 roles, 15 groups; $0 | Test permitted no-key RSS/company-feed connector on held-out slice |
| 10 | No-key RSS experiment | Zero-overlap rows 101–200: 90 identities, 90 RSS queries, 0 errors, 0 accepted mentions; discovery-only, $0 | Stop connector; obtain licensed/permitted search/jobs access or submit conservative baseline |
