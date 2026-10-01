# Signalpost

Signalpost is a deterministic, offline-first company-research agent for
Builderr's company-research contract. It validates Norwegian organisation
numbers, anchors every publication to official Brønnøysundregistrene-shaped
data, optionally enriches registry-listed static websites, and emits exactly one
terminal JSONL envelope per input. It has no LLM, API key, or runtime dependency.

## Install and run

Python 3.12.8 is the pinned development runtime (`.python-version`). The package
supports Python 3.9–3.12 and uses only the standard library:

```bash
python3 -m pip install ./signalpost
python3 -m signalpost --input signalpost/examples/input.jsonl --output out/signalpost.jsonl
```

The default adapter is a saved fixture, so the command is offline and repeatable.
To use a local JSONL corpus with the same shape as a fixture company record:

```bash
python3 -m signalpost --input companies.jsonl --adapter local-jsonl --source local-records.jsonl --output out.jsonl
```

Live BRREG access is explicit and isolated behind the adapter interface:

```bash
python3 -m signalpost --input companies.jsonl --adapter live --output out.jsonl
```

Live mode checks `robots.txt`, follows only registry-listed same-domain static
pages, enforces a request/response budget, and publishes website facts only
when the page corroborates the exact organisation number or legal name. Use
`--no-website` when testing registry-only behaviour.

For a saved BRREG bulk CSV or CSV.GZ identity snapshot:

```bash
python3 -m signalpost --input companies.jsonl --adapter bulk --source enheter.csv.gz --output out.jsonl
```

Refresh against a prior output and resume without refetching completed rows:

```bash
python3 -m signalpost --input companies.jsonl --previous out/old.jsonl --output out/new.jsonl
python3 -m signalpost --input companies.jsonl --previous out/partial.jsonl --resume --output out/resumed.jsonl
```

Run the local 100-input contract smoke report:

```bash
python3 -m signalpost.smoke --generated-count 100 --include-fixture-companies --report signalpost/reports/smoke-100.json
```

Each output object contains `state` (`available`, `not_available`, `blocked`,
`not_applicable`, `ambiguous`, or `failed`), typed profile sections, claims,
claim-level evidence spans, source snapshots, and operation metrics. Missing
values remain missing; they are never converted to zero.

## Input and local fixture shape

Input is JSONL, one object per line:

```json
{"organisation_number":"123456785","request_id":"optional"}
```

The bundled fixture demonstrates the local adapter contract. Each company has a
`modules` object containing `legal_identity`, `annual_accounts`, `leadership`,
`workplaces`, `group_links`, and optionally `annual_account_history` plus
website modules. Each module has `status_code`, `body`, and optional fixed
`retrieved_at`/`reporting_period`.

## Scope and safety

The publication gate is the exact official organisation-number match. A
mismatching identity response makes the result `ambiguous` and gates all other
facts. Missing values remain missing; they are never converted to zero. The
smoke report is a local contract report, not an official Builderr score.

See `SOURCE_POLICY.md`, `LIMITATIONS.md`, and `SUBMISSION.md` for the source
allowlist, known boundaries, and evaluator checklist.
