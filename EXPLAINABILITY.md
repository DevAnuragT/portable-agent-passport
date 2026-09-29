# How It Decides: Decision and Reasoning

The agent validates the requested task and runtime before it performs any work. Its decision reasoning selects the same framework-neutral core for every runtime, rejects unsupported runtimes or empty tasks, and uses an adapter only to translate inputs and outputs.
It can also select the repository-audit path when the caller asks for OpenGAP compliance or portability evidence.

# Inputs and Data Sources Used

The primary input is a non-empty task string, with optional metadata and a requested runtime supplied by the caller. The data sources used by the offline demo are only those caller inputs and the repository's declared identity, rules, skills, and tool definitions; it does not access private files, credentials, or remote services.
For an audit request, the input is a local repository path and the output cites only files and fields observed at that path.

# Known Limitations and Constraints

A known limitation is that the deterministic offline model demonstrates portability but does not perform live research or use a production language model. Another constraint is that local adapter tests cannot establish official OpenAI SDK, CrewAI, Claude Code, or Lyzr visas because only the HiDevs platform can verify those independent framework exports.
The repository audit is a baseline compliance check, not a complete security review, semantic code review, or official HiDevs validation.
