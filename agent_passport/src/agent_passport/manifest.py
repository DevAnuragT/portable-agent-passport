"""Framework-neutral capability manifest for an agent passport."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


@dataclass(frozen=True)
class PassportManifest:
    """Portable description of an agent's public contract."""

    name: str
    version: str
    capabilities: tuple[str, ...]
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    runtimes: tuple[str, ...]

    def validate(self) -> None:
        """Raise ValueError when the public passport contract is invalid."""
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.version.strip():
            raise ValueError("version must not be empty")
        if not self.capabilities:
            raise ValueError("at least one capability is required")
        if any(not capability.strip() for capability in self.capabilities):
            raise ValueError("capabilities must not contain empty names")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be unique")
        if not self.runtimes:
            raise ValueError("at least one runtime is required")
        if any(not runtime.strip() for runtime in self.runtimes):
            raise ValueError("runtimes must not contain empty names")
        if not isinstance(self.input_schema, Mapping):
            raise ValueError("input_schema must be a mapping")
        if not isinstance(self.output_schema, Mapping):
            raise ValueError("output_schema must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "runtimes": list(self.runtimes),
        }

    def fingerprint(self) -> str:
        """Return a stable digest for verification and audit logs."""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PassportManifest":
        manifest = cls(
            name=str(payload["name"]),
            version=str(payload["version"]),
            capabilities=tuple(payload["capabilities"]),
            input_schema=dict(payload["input_schema"]),
            output_schema=dict(payload["output_schema"]),
            runtimes=tuple(payload["runtimes"]),
        )
        manifest.validate()
        return manifest
