# Portable Agent Passport

An offline-first reference agent demonstrating that one agent contract can travel across two runtime boundaries without changing its business logic.

## Why this is portable

```text
native payload ───────┐
                      ├─> runtime adapter ─> AgentCore ─> ModelProvider
portable JSON payload ┘                         │
                                               └─> PassportManifest
```

- `AgentCore` contains the business logic and depends only on small Python protocols.
- `NativeRuntimeAdapter` handles direct Python payloads.
- `PortableJsonAdapter` handles JSON-shaped data and returns JSON-serialisable output.
- `PassportManifest` is the verifiable public contract.
- `verify` checks manifest validity, adapter parity, deterministic replay, and invalid-input rejection.

## Run without an API key

From the repository root:

```bash
PYTHONPATH=agent_passport/src python3 -m unittest discover -s agent_passport/tests -v
PYTHONPATH=agent_passport/src python3 -m agent_passport verify
PYTHONPATH=agent_passport/src python3 -m agent_passport run "summarise the portability goal" --runtime native
PYTHONPATH=agent_passport/src python3 -m agent_passport run "summarise the portability goal" --runtime portable-json
```

The demo model is deliberately deterministic and offline. A production model can be added by implementing `ModelProvider.generate(prompt)`, without changing the core or adapters.

## Evidence

Latest local run: **8 tests passed**. The verification command prints a manifest fingerprint and four passing checks. The organizer's score is not claimed here; only official challenge checkpoints can establish that score.

## Reproducibility and safety

- No network call, API key, database, or external service is required.
- Invalid empty tasks are rejected before model execution.
- Outputs include runtime, passport fingerprint, and a small execution trace.
- Tests use only the Python standard library.

## Challenge submission checklist

- [ ] Register before the deadline shown by the organizer.
- [ ] Read and satisfy every official verification checkpoint.
- [ ] Attach the repository and a short demo showing both runtimes.
- [ ] Include the verification output and commit/release identifier.
- [ ] Replace the offline demo provider with an allowed production provider only if the rules require it.
- [ ] Verify every external link and submission field before final submission.
