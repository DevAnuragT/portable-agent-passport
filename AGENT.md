# Signalpost Agent Brief

## Mission

Build a reproducible company-research agent for Builderr Signalpost.

Input: Norwegian organisation number (`org.nr`).

Output: one evidence-backed, current company profile. Every material claim must belong to the exact requested company and include source, retrieval time, and reporting/effective date where relevant.

Primary rule: a missing fact is safer than an invented fact or a wrong-company fact.

## Current challenge facts

- Challenge: Signalpost — Build an agent that finds company information online.
- Official page: <https://builderr.ai/challenges/signalpost>
- Round: 23 August–21 October 2026.
- Official batch: Builderr supplies the same hidden company batch to every eligible frozen entry. Current shared set is 1,000 companies and may grow to 1,100.
- Public universe: 411,160 eligible Norwegian entities with observed 2025 annual-account records.
- Local test: required 100-company smoke test. Larger local tests are encouraged, but precomputed profiles do not become the scored entry.
- Qualification: at least 65/100 on an official run.
- Revisions: initial submission plus up to four revised exact commits; revision window closes 18 October 2026.
- Submission: email `submit@builderr.ai`.

### Score

- 50: recall and coverage
- 30: precision, exact-company matching, and evidence
- 12: useful synthesis
- 8: UX and verification ease

Coverage weighting per information family: 70% company recall, 30% individual-claim recall.

Material wrong-company publication or fabricated financial value can prevent an official run from qualifying.

## Required behavior

Return exactly one terminal envelope for every input company, including companies for which nothing was found.

Valid terminal states:

- `available`
- `not_available`
- `blocked`
- `not_applicable`
- `ambiguous`
- `failed`

Never drop a company. Never convert missing data into zero.

Each result should cover, when available:

1. Legal identity and public brand
2. Latest annual accounts and useful history
3. Leadership and registered workplaces
4. Verified official website and company-owned profiles
5. Hiring and dated public activity from permitted sources
6. Claim-level evidence and availability state
7. Refresh metadata and material changes since the previous run

Recommended claim fields:

```text
field, value, status, source_url, source_name, source_quote,
retrieved_at, published_at, reporting_period, content_hash,
extraction_method, confidence
```

## Identity and safety gates

Official Norwegian data is the identity anchor. Do not publish a web fact unless the source resolves to the exact legal entity.

Hard checks:

- exact organisation-number match whenever present
- legal-name match
- address or municipality corroboration
- domain ownership/association through official registry or verified company site
- parent, subsidiary, group, franchise, and public-brand relationships labelled separately
- conflicting facts preserved as evidence; never silently overwrite

If identity remains uncertain, publish `ambiguous` or `not_available`.

## Permitted-source policy

Preferred sources:

- Brønnøysundregistrene Enhetsregisteret: identity, legal form, address, industry, registered employees
- Regnskapsregisteret and annual-account copies: filed financial data and history
- Official roles endpoints: management and board roles
- Official subunit records: registered workplaces
- Verified company website: sitemap, about, contact, leadership, locations, careers, news, structured data
- Official or licensed APIs and public pages whose terms and robots policy allow the access pattern

Rules:

- Search results are discovery only, not claim evidence.
- Record source URL/identifier, retrieval time, effective/reporting date, content hash, and extraction method.
- Do not scrape LinkedIn, Meta, Glassdoor, Indeed, Google, or similar platforms through unofficial connectors unless access is permitted and claims are independently verified.
- Declare source rights, outbound URL policy, and any external cache.

## Architecture

```text
org.nr
  -> validate
  -> official identity lookup
  -> permitted-source discovery
  -> fetch with cache, timeout, retry, and request budget
  -> deterministic parsing first
  -> exact-company matching
  -> fact normalization and conflict resolution
  -> freshness/change detection
  -> evidence-backed terminal envelope
```

Recommended baseline:

- Python 3.12+
- `httpx`, `pydantic`, `selectolax`/`BeautifulSoup`
- SQLite or DuckDB for snapshots, attempts, and reports
- `pytest`
- `RapidFuzz` only after hard identity checks
- browser rendering only for confirmed JavaScript shells
- PDF text extraction first; layout/OCR fallback only when needed

Keep deterministic parsers on the critical path. Use an LLM only for narrow, evidence-grounded extraction or synthesis.

## LLM/API policy

An LLM API is **not required**. The agent should work for registry facts, structured data, ordinary HTML, annual accounts, identity checks, evidence storage, and output validation without an LLM.

This is preferred because it improves reproducibility, cost, latency, and evaluator portability.

Use an LLM only when it adds measurable coverage:

- extracting facts from messy prose after deterministic extraction fails
- classifying company-owned pages
- producing a concise summary from already accepted claims
- translating/normalizing Norwegian text while preserving source evidence

Never allow an LLM to invent values, URLs, dates, identity matches, or financial figures. Require structured JSON, validate it, and reject any claim without source-span evidence.

### Recommended development providers

Provider quotas change. Verify active limits before use.

1. **Google Gemini API** — preferred quality/flexibility option for local experiments; use a Flash-class model and structured output. Google documents free-tier limits in AI Studio and says active limits are account/project-specific.
2. **Groq** — preferred high-throughput fallback for small extraction jobs. Its current free-plan documentation lists, for several open models, 1,000 requests/day, 200,000 tokens/day, and 8,000 tokens/minute. Exact limits remain account/model dependent.

Keep provider access behind an adapter:

```text
LLM_PROVIDER=none|gemini|groq
GEMINI_API_KEY=...
GROQ_API_KEY=...
LLM_MODEL=...
```

Do not commit keys. Use environment variables or evaluator-provided secrets.

### Official evaluation key

Builderr states that an evaluator model key can be supplied if needed, and that an entrant's personal credential cannot be used for a reproducible official run. Therefore:

- prefer `LLM_PROVIDER=none` for the baseline;
- if an LLM materially improves the agent, declare model/API/licence and ask Builderr for an evaluator key before submission;
- do not make scoring depend on an unshareable personal free-tier key.

## Refresh and learning

Persist:

- raw snapshot hashes
- requested URLs and redirects
- source responses/errors
- candidate domains and claims
- accepted and rejected claims with reasons
- identity evidence
- runtime, request count, and cost
- previous profile and change events

Refresh must preserve prior evidence. Failed refresh must not erase the last supported value. Use typed changes such as `new_role`, `new_location`, `new_filing`, `closed_job`, or `changed_description`.

Use a strategy registry. Promote a new strategy only when it causes zero new material wrong-company publications, does not reduce precision/evidence validity, improves useful coverage, and stays within runtime/request/cost limits. Freeze code, dependencies, prompts, models, thresholds, source allowlist, and routing before each official daily batch.

## Local evaluation loop

Build a 100-company smoke test that verifies:

- one terminal envelope per input
- deterministic schema
- identity precision
- source/evidence linkage
- honest missing/blocked states
- refresh idempotency
- change detection
- timeout/retry behavior
- clean-install reproducibility
- request count, runtime, and API cost

Then scale to 1,000+ public-universe companies. Public outputs are development evidence, not the official score.

Track:

```text
exact-company precision
wrong-company count
field precision/recall/coverage
evidence validity
crawl completion
refresh correctness
false-change rate
request count
cost per company
p50/p95 runtime
```

## Submission checklist

Send `submit@builderr.ai`:

- repository URL
- exact commit hash
- 100-company smoke-test result/report
- one command to run the agent
- models, APIs, and licences
- expected cost per official run
- agent name
- contact for results

Clean-machine requirements:

- pinned dependencies and lockfile
- no local-only files or secrets
- one install step
- one pasteable evaluator command
- exactly one result per supplied company

## Official references

- Challenge: <https://builderr.ai/challenges/signalpost>
- Brief: <https://builderr.ai/starter-briefs/signalpost.md>
- Source policy: <https://builderr.ai/starter-briefs/signalpost-sources.md>
- Learning harness: <https://builderr.ai/starter-briefs/signalpost-learning-harness.md>
- Evaluation contract: <https://builderr.ai/docs/signalpost-evaluation-harness.md>
- Starter kit: <https://builderr.ai/signalpost-starter-kit.tar.gz>
- Public company universe: <https://builderr.ai/signalpost-company-universe-2025.jsonl.gz>
- Submission email: `submit@builderr.ai`
