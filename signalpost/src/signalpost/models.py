"""Typed input, output, claim, and evidence models for the Signalpost contract.

The package deliberately uses dataclasses instead of a runtime validation library so a
clean evaluator install has no dependency or API-key requirements.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .validation import validate_organisation_number


class Availability(str, Enum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"


TerminalState = Availability


class ValidationError(ValueError):
    """Raised when a typed contract object cannot be constructed safely."""


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_timestamp(value: str, name: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T[^ ]+Z", value):
        raise ValidationError(f"{name} must be an RFC3339 UTC timestamp ending in Z")


def _require_url(value: str, name: str = "source_url") -> None:
    if not isinstance(value, str) or not (value.startswith("https://") or value.startswith("http://")):
        raise ValidationError(f"{name} must be an HTTP(S) URL")


@dataclass(frozen=True)
class CompanyInput:
    organisation_number: str
    request_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "organisation_number", validate_organisation_number(self.organisation_number))
        if self.request_id is not None and not isinstance(self.request_id, str):
            raise ValidationError("request_id must be a string")

    @classmethod
    def from_json(cls, value: Any) -> "CompanyInput":
        if isinstance(value, str):
            return cls(value)
        if not isinstance(value, Mapping):
            raise ValidationError("each JSONL input line must be a string or object")
        if "organisation_number" not in value:
            raise ValidationError("input object requires organisation_number")
        known = {"organisation_number", "request_id", "metadata"}
        extra = set(value) - known
        if extra:
            raise ValidationError(f"unknown input fields: {sorted(extra)}")
        return cls(str(value["organisation_number"]), value.get("request_id"), value.get("metadata") or {})

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"organisation_number": self.organisation_number}
        if self.request_id is not None:
            result["request_id"] = self.request_id
        if self.metadata:
            result["metadata"] = _json_value(self.metadata)
        return result


@dataclass(frozen=True)
class EvidenceSpan:
    locator: str
    quote: str
    kind: str = "json_pointer"

    def __post_init__(self) -> None:
        if not self.locator or not self.quote:
            raise ValidationError("evidence span requires locator and quote")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "locator": self.locator, "quote": self.quote}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceSpan":
        return cls(str(value.get("locator", "")), str(value.get("quote", "")), str(value.get("kind", "json_pointer")))


@dataclass(frozen=True)
class Evidence:
    id: str
    source_url: str
    source_name: str
    source_class: str
    retrieved_at: str
    content_hash: str
    span: EvidenceSpan
    extraction_method: str = "deterministic_json"
    published_at: Optional[str] = None
    reporting_period: Optional[str] = None
    snapshot_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id or not self.source_name or not self.source_class:
            raise ValidationError("evidence requires id, source_name, and source_class")
        _require_url(self.source_url)
        _require_timestamp(self.retrieved_at, "retrieved_at")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ValidationError("content_hash must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "source_class": self.source_class,
            "retrieved_at": self.retrieved_at,
            "published_at": self.published_at,
            "reporting_period": self.reporting_period,
            "content_hash": self.content_hash,
            "extraction_method": self.extraction_method,
            "span": self.span.to_dict(),
            "snapshot_id": self.snapshot_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Evidence":
        return cls(
            str(value["id"]), str(value["source_url"]), str(value.get("source_name", "")), str(value.get("source_class", "")),
            str(value["retrieved_at"]), str(value["content_hash"]), EvidenceSpan.from_dict(value.get("span", {})),
            str(value.get("extraction_method", "deterministic_json")), value.get("published_at"), value.get("reporting_period"), value.get("snapshot_id"),
        )


@dataclass(frozen=True)
class Claim:
    id: str
    field: str
    value: Any
    availability: Availability
    evidence_ids: Sequence[str] = field(default_factory=tuple)
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.id or not self.field:
            raise ValidationError("claim requires id and field")
        if self.availability is Availability.AVAILABLE and not self.evidence_ids:
            raise ValidationError("available claims require evidence_ids")
        if self.availability is not Availability.AVAILABLE and self.value is not None:
            raise ValidationError("unavailable claims must not turn missing data into a value")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValidationError("confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "field": self.field,
            "value": _json_value(self.value),
            "availability": self.availability.value,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Claim":
        return cls(str(value["id"]), str(value["field"]), value.get("value"), Availability(str(value["availability"])), tuple(value.get("evidence_ids", ())), value.get("confidence"))


@dataclass(frozen=True)
class SourceSnapshot:
    id: str
    source_url: str
    retrieved_at: str
    content_hash: str
    status_code: Optional[int]
    source_class: str = "official_registry"
    error: Optional[str] = None

    def __post_init__(self) -> None:
        _require_url(self.source_url)
        _require_timestamp(self.retrieved_at, "retrieved_at")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ValidationError("snapshot content_hash must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "content_hash": self.content_hash,
            "status_code": self.status_code,
            "source_class": self.source_class,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceSnapshot":
        return cls(str(value["id"]), str(value["source_url"]), str(value["retrieved_at"]), str(value["content_hash"]), value.get("status_code"), str(value.get("source_class", "official_registry")), value.get("error"))


@dataclass(frozen=True)
class ProfileSection:
    availability: Availability
    claim_ids: Sequence[str] = field(default_factory=tuple)
    note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"availability": self.availability.value, "claim_ids": list(self.claim_ids), "note": self.note}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProfileSection":
        return cls(Availability(str(value["availability"])), tuple(value.get("claim_ids", ())), value.get("note"))


@dataclass(frozen=True)
class CompanyProfile:
    legal_identity: ProfileSection
    annual_accounts: ProfileSection
    leadership: ProfileSection
    workplaces: ProfileSection
    group_links: ProfileSection
    official_website: ProfileSection
    hiring_and_activity: ProfileSection

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_identity": self.legal_identity.to_dict(),
            "annual_accounts": self.annual_accounts.to_dict(),
            "leadership": self.leadership.to_dict(),
            "workplaces": self.workplaces.to_dict(),
            "group_links": self.group_links.to_dict(),
            "official_website": self.official_website.to_dict(),
            "hiring_and_activity": self.hiring_and_activity.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CompanyProfile":
        return cls(*(ProfileSection.from_dict(value[name]) for name in ("legal_identity", "annual_accounts", "leadership", "workplaces", "group_links", "official_website", "hiring_and_activity")))


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    started_at: str
    completed_at: str
    terminal_status: Availability

    def __post_init__(self) -> None:
        _require_timestamp(self.started_at, "started_at")
        _require_timestamp(self.completed_at, "completed_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "terminal_status": self.terminal_status.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RunMetadata":
        return cls(str(value["run_id"]), str(value["started_at"]), str(value["completed_at"]), Availability(str(value["terminal_status"])))


@dataclass(frozen=True)
class OperationMetrics:
    requests: int
    runtime_ms: int
    third_party_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.requests < 0 or self.runtime_ms < 0 or self.third_party_cost_usd < 0:
            raise ValidationError("operation metrics cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {"requests": self.requests, "runtime_ms": self.runtime_ms, "third_party_cost_usd": self.third_party_cost_usd}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OperationMetrics":
        return cls(int(value.get("requests", 0)), int(value.get("runtime_ms", 0)), float(value.get("third_party_cost_usd", 0.0)))


@dataclass(frozen=True)
class ErrorRecord:
    code: str
    message: str
    module: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "module": self.module}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ErrorRecord":
        return cls(str(value["code"]), str(value["message"]), value.get("module"))


@dataclass(frozen=True)
class ChangeEvent:
    field: str
    change_type: str
    previous_value: Any
    current_value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "change_type": self.change_type, "previous_value": _json_value(self.previous_value), "current_value": _json_value(self.current_value)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ChangeEvent":
        return cls(str(value["field"]), str(value["change_type"]), value.get("previous_value"), value.get("current_value"))


@dataclass(frozen=True)
class OutputEnvelope:
    organisation_number: str
    state: Availability
    run: RunMetadata
    profile: CompanyProfile
    claims: Sequence[Claim] = field(default_factory=tuple)
    evidence: Sequence[Evidence] = field(default_factory=tuple)
    snapshots: Sequence[SourceSnapshot] = field(default_factory=tuple)
    changes: Sequence[ChangeEvent] = field(default_factory=tuple)
    errors: Sequence[ErrorRecord] = field(default_factory=tuple)
    operations: OperationMetrics = field(default_factory=lambda: OperationMetrics(0, 0))

    def __post_init__(self) -> None:
        object.__setattr__(self, "organisation_number", validate_organisation_number(self.organisation_number))
        if self.run.terminal_status is not self.state:
            raise ValidationError("run terminal_status must match envelope state")
        evidence_ids = {item.id for item in self.evidence}
        claim_ids = {item.id for item in self.claims}
        if len(evidence_ids) != len(self.evidence) or len(claim_ids) != len(self.claims):
            raise ValidationError("claim and evidence ids must be unique")
        snapshot_ids = {item.id for item in self.snapshots}
        for claim in self.claims:
            if not set(claim.evidence_ids) <= evidence_ids:
                raise ValidationError(f"claim {claim.id} references missing evidence")
        for item in self.evidence:
            if item.snapshot_id is not None and item.snapshot_id not in snapshot_ids:
                raise ValidationError(f"evidence {item.id} references missing snapshot")
        for section in self.profile.to_dict().values():
            if not set(section["claim_ids"]) <= claim_ids:
                raise ValidationError("profile section references missing claim")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organisation_number": self.organisation_number,
            "state": self.state.value,
            "run": self.run.to_dict(),
            "profile": self.profile.to_dict(),
            "claims": [claim.to_dict() for claim in self.claims],
            "evidence": [item.to_dict() for item in self.evidence],
            "snapshots": [item.to_dict() for item in self.snapshots],
            "changes": [item.to_dict() for item in self.changes],
            "errors": [item.to_dict() for item in self.errors],
            "operations": self.operations.to_dict(),
        }

    def json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OutputEnvelope":
        return cls(
            str(value["organisation_number"]), Availability(str(value["state"])), RunMetadata.from_dict(value["run"]), CompanyProfile.from_dict(value["profile"]),
            tuple(Claim.from_dict(item) for item in value.get("claims", ())), tuple(Evidence.from_dict(item) for item in value.get("evidence", ())),
            tuple(SourceSnapshot.from_dict(item) for item in value.get("snapshots", ())), tuple(ChangeEvent.from_dict(item) for item in value.get("changes", ())),
            tuple(ErrorRecord.from_dict(item) for item in value.get("errors", ())), OperationMetrics.from_dict(value.get("operations", {})),
        )
