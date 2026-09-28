"""Framework-neutral execution contract for the passport agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from .manifest import PassportManifest


class ModelProvider(Protocol):
    """Smallest model contract required by the agent core."""

    def generate(self, prompt: str) -> str:
        ...


class Tool(Protocol):
    """Optional deterministic tool contract."""

    name: str

    def run(self, argument: str) -> str:
        ...


@dataclass(frozen=True)
class AgentRequest:
    """Portable request object; adapters translate into this type."""

    task: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.task, str) or not self.task.strip():
            raise ValueError("task must be a non-empty string")


@dataclass(frozen=True)
class AgentResponse:
    """Portable response with enough information for verification."""

    answer: str
    runtime: str
    passport_fingerprint: str
    trace: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "runtime": self.runtime,
            "passport_fingerprint": self.passport_fingerprint,
            "trace": list(self.trace),
        }


class AgentCore:
    """Business logic independent of a web framework or agent framework."""

    def __init__(self, manifest: PassportManifest, model: ModelProvider, tools: tuple[Tool, ...] = ()) -> None:
        manifest.validate()
        self.manifest = manifest
        self.model = model
        self.tools = {tool.name: tool for tool in tools}

    def run(self, request: AgentRequest, *, runtime: str) -> AgentResponse:
        request.validate()
        if runtime not in self.manifest.runtimes:
            raise ValueError(f"unsupported runtime: {runtime}")
        prompt = self._prompt(request)
        answer = self.model.generate(prompt).strip()
        if not answer:
            raise RuntimeError("model returned an empty answer")
        return AgentResponse(
            answer=answer,
            runtime=runtime,
            passport_fingerprint=self.manifest.fingerprint(),
            trace=(f"runtime:{runtime}", "model:generate"),
        )

    def _prompt(self, request: AgentRequest) -> str:
        return f"You are {self.manifest.name}. Complete this task clearly and concisely:\n{request.task.strip()}"
