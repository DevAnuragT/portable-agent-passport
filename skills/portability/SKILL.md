---
name: portability
description: Explain portable agent architecture, runtime migration, and verification.
---

# Portability advisor skill

## Purpose

Explain how to preserve an agent's identity and behaviour while moving it between runtimes.

## Procedure

1. Inspect the passport manifest and declared capabilities.
2. Separate framework-neutral business logic from runtime adapters.
3. Compare input and output contracts across adapters.
4. Run deterministic replay and invalid-input checks.
5. Report local evidence separately from official platform verification.

## Safety

Never invent a framework export, checkpoint receipt, visa, leaderboard position, or score.
