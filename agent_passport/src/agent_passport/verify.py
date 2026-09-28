"""Local verification checks for the Agent Passport contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .adapters import NativeRuntimeAdapter, PortableJsonAdapter
from .core import AgentCore


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_checks(core: AgentCore) -> tuple[CheckResult, ...]:
    checks: tuple[Callable[[AgentCore], CheckResult], ...] = (
        _check_manifest,
        _check_adapter_parity,
        _check_replay,
        _check_rejection,
    )
    return tuple(check(core) for check in checks)


def _check_manifest(core: AgentCore) -> CheckResult:
    try:
        core.manifest.validate()
        return CheckResult("manifest-valid", True, core.manifest.fingerprint())
    except Exception as exc:  # pragma: no cover - defensive boundary
        return CheckResult("manifest-valid", False, str(exc))


def _check_adapter_parity(core: AgentCore) -> CheckResult:
    payload = {"task": "state the portability goal"}
    native = NativeRuntimeAdapter(core).execute(payload)
    portable = PortableJsonAdapter(core).execute(payload)
    passed = native["answer"] == portable["answer"] and native["passport_fingerprint"] == portable["passport_fingerprint"]
    return CheckResult("adapter-parity", passed, "same answer and passport fingerprint")


def _check_replay(core: AgentCore) -> CheckResult:
    adapter = NativeRuntimeAdapter(core)
    first = adapter.execute({"task": "replay me"})
    second = adapter.execute({"task": "replay me"})
    return CheckResult("deterministic-replay", first == second, "identical input produces identical output")


def _check_rejection(core: AgentCore) -> CheckResult:
    try:
        NativeRuntimeAdapter(core).execute({"task": ""})
    except ValueError:
        return CheckResult("invalid-input-rejected", True, "empty task rejected")
    return CheckResult("invalid-input-rejected", False, "empty task was accepted")
