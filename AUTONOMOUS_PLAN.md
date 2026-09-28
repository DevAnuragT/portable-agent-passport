# Agent Passport Challenge — Autonomous Build Plan

## Operating rule

Run continuously without waiting for chat approval. For every feature, use this loop:

1. **Plan** — define one small outcome, acceptance checks, files, and risks.
2. **Build** — implement only that outcome; prefer simple, portable code.
3. **Review** — inspect the diff for correctness, portability, security, and challenge fit.
4. **Test** — run focused tests, then the full available test suite when practical.
5. **Record** — append short bullets to `progress.md`; record verified points in `scores.md`.
6. **Continue** — immediately start the next incomplete feature.

Do not pause for suggestions or confirmation. Make reasonable defaults, keep scope tight, and recover from failures by fixing the smallest blocking issue. Never commit credentials, tokens, private data, or fabricated judging results. External registration, uploads, and final submission remain manual unless an explicitly authorised integration is available.

## Default project direction

Build a **Portable Agent Passport**: one useful agent with a framework-independent core, interchangeable runtime adapters, a capability manifest, deterministic verification tests, and production-grade documentation.

Suggested stack: Python, typed interfaces, JSON schemas, pytest, and Docker where useful. The core must remain runnable without paid APIs by using deterministic fake providers in tests.

## Feature sequence

- [x] F0 — Repository scaffold, coding conventions, test runner, and tracking files.
- [x] F1 — Agent capability manifest and passport schema.
- [x] F2 — Framework-neutral agent core with tool and model interfaces.
- [x] F3 — Two runtime adapters using the same core contract.
- [x] F4 — Verification harness: portability, schema, replay, and failure tests.
- [x] F5 — Minimal useful demo workflow and CLI/API entry point.
- [x] F6 — Containerised/reproducible execution and example configuration.
- [x] F7 — README, architecture diagram, verification evidence, and short demo script.
- [x] F8 — Final local review and submission checklist.

## Definition of done for each feature

- Acceptance criteria are explicit and met.
- Tests cover the new behaviour and failure paths.
- No secrets or machine-specific paths are committed.
- A new contributor can reproduce the result from the documentation.
- `progress.md` and `scores.md` are updated in the same loop.

## Recovery rules

- Test failure: reproduce, isolate, fix, rerun focused test, then rerun regression tests.
- Ambiguous requirement: choose the smallest reversible interpretation and document it.
- Missing dependency or credential: use a local deterministic substitute and record the limitation.
- Time pressure: prioritise verification, portability, documentation, and a reliable demo over extra features.
