# Submission checklist

## Reproducible local command

```bash
python3 -m venv .venv
.venv/bin/python -m pip install ./signalpost
.venv/bin/python -m signalpost --input companies.jsonl --adapter live --output out.jsonl
```

For an offline check:

```bash
.venv/bin/python -m signalpost --input signalpost/examples/input.jsonl --output out.jsonl
```

## Local verification

```bash
.venv/bin/python -m unittest discover -s signalpost/tests -v
.venv/bin/python -m signalpost.smoke --generated-count 100 --include-fixture-companies --report signalpost/reports/smoke-100.json
```

The smoke report records terminal-envelope count, state distribution, request
count, runtime, cost, evidence linkage, and wrong-company checks. It explicitly
sets `official_score_claimed` to `false`.

## Before official submission

- Run the supplied official batch, not the generated smoke input.
- Record the exact commit and freeze code/configuration.
- Declare the BRREG API and registry-listed website source policy.
- Provide the smoke report and evaluator command.
- Do not include credentials, private caches, or precomputed official profiles.
