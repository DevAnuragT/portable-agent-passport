# Decision

The agent first validates the task and identifies whether the request concerns portability, verification, runtime migration, or general agent behaviour. It then selects the smallest deterministic response path and includes the relevant contract or limitation.

The decision is based on the task text and the declared passport capabilities, not on hidden state. When a framework-specific operation is requested, the agent explains the adapter boundary instead of pretending all frameworks behave identically.

# Inputs

The primary input is a task string supplied by the caller. Optional metadata may identify the requested runtime, source framework, target framework, or verification context.

The agent uses only caller-provided data and its declared portability guidance. The offline demo does not access private files, credentials, or remote data sources.

# Limits

The demo provider is deterministic and offline, so it does not perform live web research or call a commercial model. Its local verification result is not an official HiDevs checkpoint result; this is a known issue when evaluating production readiness.

The current implementation demonstrates an adapter contract but cannot prove compatibility with every version of OpenAI SDK, CrewAI, Claude Code, or Lyzr without running those environments. Framework-specific failures must be tested in the designated platform.
