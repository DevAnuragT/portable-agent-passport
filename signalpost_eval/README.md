# Signalpost local evaluator

`signalpost_eval` is a standalone, standard-library-only Phase 4 smoke evaluator.
It does not import or execute Signalpost, call an API, use an LLM, or claim an
official Builderr score. It consumes the documented input JSONL and terminal
envelope JSONL streams and writes a deterministic machine-readable report.

```bash
python3 -m signalpost_eval \
  --inputs signalpost/examples/input.jsonl \
  --outputs out/signalpost.jsonl \
  --report out/signalpost-evaluation.json \
  --strict
```

The report includes schema/cardinality, exact identity, evidence-span support,
availability, refresh/change, request/cost, and runtime summaries. Non-empty input
lines are paired positionally with output lines; a count mismatch is always
reported. `--strict` exits nonzero for a failed local contract check.

The regression fixtures under `fixtures/` intentionally contain a wrong-company
identity and an unsupported claim. They should fail local checks, demonstrating
that the evaluator catches those conditions. These are test artifacts, not an
official Builderr result.
