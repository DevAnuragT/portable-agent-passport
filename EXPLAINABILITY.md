# Overview

This agent is a portability advisor for developers building and migrating AI agents. It preserves an explicit identity, input contract, output contract, and verification trail while runtime adapters change around the core.

# Decision

The agent first validates the task and identifies whether the request concerns portability, verification, runtime migration, or general agent behaviour. It then selects the smallest deterministic response path and includes the relevant contract or limitation.

The decision is based on the task text and the declared passport capabilities, not on hidden state. When a framework-specific operation is requested, the agent explains the adapter boundary instead of pretending all frameworks behave identically.

# Inputs

The primary input is a task string supplied by the caller. Optional metadata may identify the requested runtime, source framework, target framework, or verification context.

The agent uses only caller-provided data and its declared portability guidance. The offline demo does not access private files, credentials, or remote data sources.

# Outputs

The agent returns a JSON-serialisable response containing an answer, the runtime used, the passport fingerprint, and a short execution trace. The response contract is kept stable so an adapter can translate transport details without changing the core result.

# Tools

The repository provides a run tool for executing the agent and a verification tool for running the local passport checks. Tool execution is deterministic in the demo and does not require network access or an API key.

# Skills

The portability-advisor skill explains how to separate framework-neutral business logic from runtime-specific adapters. It also instructs the agent to distinguish local evidence from official HiDevs verification.

# Verification

Verification checks manifest validity, adapter parity, deterministic replay, and rejection of an empty task. These checks provide reproducible local evidence, but only the designated HiDevs platform can issue official checkpoints and framework visas.

# Safety

The agent does not request credentials, access private repositories, or claim official scores without a platform receipt. Third-party frameworks and models must be disclosed when they are added to the implementation.

# Portability

The same AgentCore is exposed through native, portable JSON, OpenAI-shaped, CrewAI-shaped, Claude-Code-shaped, and Lyzr-shaped entrypoints. The local wrappers prove the shared contract, while actual framework compatibility must be confirmed in each independent execution environment.

# Limits

The demo provider is deterministic and offline, so it does not perform live web research or call a commercial model. Its local verification result is not an official HiDevs checkpoint result; this is a known issue when evaluating production readiness.

The current implementation demonstrates an adapter contract but cannot prove compatibility with every version of OpenAI SDK, CrewAI, Claude Code, or Lyzr without running those environments. Framework-specific failures must be tested in the designated platform.
