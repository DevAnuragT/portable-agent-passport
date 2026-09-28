# Submission checklist

## Local readiness

- [x] Framework-neutral core exists.
- [x] Two runtime adapters execute the same task contract.
- [x] Passport manifest is checked in and validates.
- [x] Verification checks pass offline.
- [x] Invalid input is rejected.
- [x] README includes setup, architecture, evidence, and demo commands.
- [x] No credentials, tokens, or network dependencies are included.
- [x] Dockerfile is provided for reproducible execution.
- [ ] A useful specialised agent is demonstrated, rather than only the offline echo demo.
- [ ] Migration between recognised frameworks/runtimes is demonstrated.
- [ ] At least one concrete tool is used and verified.
- [ ] Behaviour and identity contracts are tested at capability level.
- [ ] A public demo/deep-dive explains practical impact.

## Manual organizer actions

- [ ] Register on the official challenge page.
- [x] Public GitHub repository created: `https://github.com/DevAnuragT/portable-agent-passport`.
- [ ] Confirm the exact checkpoint rubric, required runtimes, and submission format.
- [ ] Replace or extend the demo provider only when permitted by the rubric.
- [ ] Record each official checkpoint receipt and points in `scores.md`.
- [ ] Submit the repository, verification output, and demo link before the deadline.

## Current evidence

- Test suite: 8 passing tests.
- Verification: 4/4 checks passing.
- Manifest fingerprint: `c3181968e3e886c1a6a57fd1e8fa3e9c2506c92e9c3d5595bdb570cfe911f410`.
- Container build: not locally verified because the Docker daemon was unavailable; Dockerfile received static review.
- Rule audit: see `CHALLENGE_AUDIT.md`.
