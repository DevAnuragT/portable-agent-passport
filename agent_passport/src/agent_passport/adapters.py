"""Two intentionally thin runtime adapters over the same agent core."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .core import AgentCore, AgentRequest, AgentResponse


class RuntimeAdapter(Protocol):
    runtime: str

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        ...


class NativeRuntimeAdapter:
    """Direct Python adapter."""

    runtime = "native"

    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        response = self.core.run(_request_from_payload(payload), runtime=self.runtime)
        return response.to_dict()


class PortableJsonAdapter:
    """JSON-shaped adapter representing a second ecosystem boundary."""

    runtime = "portable-json"

    def __init__(self, core: AgentCore) -> None:
        self.core = core

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        # Explicitly copy fields to prove the adapter does not leak framework objects.
        request = {"task": str(payload.get("task", "")), "metadata": dict(payload.get("metadata", {}))}
        response = self.core.run(_request_from_payload(request), runtime=self.runtime)
        return response.to_dict()


def _request_from_payload(payload: Mapping[str, Any]) -> AgentRequest:
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be an object")
    return AgentRequest(task=payload.get("task", ""), metadata={str(k): str(v) for k, v in metadata.items()})
