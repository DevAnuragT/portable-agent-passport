"""Immutable, deterministic claim refresh and change detection.

Refresh is deliberately independent from network transport.  Callers provide
JSON-compatible claim/evidence records produced by a connector.  A failed or
blocked refresh never erases the last supported value.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _available(claim: Mapping[str, Any]) -> bool:
    return claim.get("availability") == "available" and claim.get("value") is not None


def claim_key(claim: Mapping[str, Any]) -> str:
    """Stable logical key; source URL separates same-field multi-source claims."""

    explicit = claim.get("stable_key")
    if explicit:
        return str(explicit)
    field = str(claim.get("field") or "unknown")
    source = str(claim.get("source_url") or "")
    return f"{field}|{source}" if source else field


def _index(claims: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for claim in claims:
        key = claim_key(claim)
        # Duplicate logical claims are retained deterministically by suffixing
        # their key instead of silently overwriting one observation.
        if key in result:
            suffix = 2
            while f"{key}#{suffix}" in result:
                suffix += 1
            key = f"{key}#{suffix}"
        result[key] = claim
    return result


def _evidence_index(evidence: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("id")): item for item in evidence if item.get("id")}


@dataclass(frozen=True)
class RefreshResult:
    claims: tuple[dict[str, Any], ...]
    evidence: tuple[dict[str, Any], ...]
    changes: tuple[dict[str, Any], ...]
    retained_after_failure: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims": [copy.deepcopy(item) for item in self.claims],
            "evidence": [copy.deepcopy(item) for item in self.evidence],
            "changes": [copy.deepcopy(item) for item in self.changes],
            "retained_after_failure": self.retained_after_failure,
        }


def refresh_claims(
    previous_claims: Sequence[Mapping[str, Any]],
    previous_evidence: Sequence[Mapping[str, Any]],
    current_claims: Sequence[Mapping[str, Any]],
    current_evidence: Sequence[Mapping[str, Any]],
    *,
    refresh_state: str = "available",
) -> RefreshResult:
    """Merge a refresh while preserving immutable historical evidence.

    ``refresh_state`` is the connector terminal state.  When it is ``failed``,
    ``blocked`` or ``ambiguous``, the current values are not treated as a full
    observation: previous supported claims remain current and no removals are
    emitted.  Replaying identical inputs is byte-stable.
    """

    previous = _index(previous_claims)
    prior_evidence = _evidence_index(previous_evidence)
    # Evidence is immutable.  If a connector reuses an id for changed bytes,
    # retain both observations and rewrite only the current claim reference.
    evidence_id_map: dict[str, str] = {}
    normalised_current_evidence: list[dict[str, Any]] = []
    for raw_item in current_evidence:
        item = copy.deepcopy(dict(raw_item))
        original_id = str(item.get("id") or "")
        if not original_id:
            continue
        replacement = original_id
        if original_id in prior_evidence and _canonical(prior_evidence[original_id]) != _canonical(item):
            replacement = f"{original_id}-{_digest(item)[:8]}"
        evidence_id_map[original_id] = replacement
        item["id"] = replacement
        normalised_current_evidence.append(item)

    normalised_current_claims: list[dict[str, Any]] = []
    for raw_claim in current_claims:
        item = copy.deepcopy(dict(raw_claim))
        item["evidence_ids"] = [evidence_id_map.get(str(ref), str(ref)) for ref in item.get("evidence_ids", [])]
        normalised_current_claims.append(item)

    current = _index(normalised_current_claims)
    failed = refresh_state in {"failed", "blocked", "ambiguous"}
    merged: dict[str, dict[str, Any]] = {key: copy.deepcopy(dict(value)) for key, value in previous.items()}
    evidence: dict[str, dict[str, Any]] = {
        key: copy.deepcopy(dict(value)) for key, value in prior_evidence.items()
    }
    for item in normalised_current_evidence:
        if item.get("id"):
            evidence.setdefault(str(item["id"]), copy.deepcopy(dict(item)))

    changes: list[dict[str, Any]] = []
    if not failed:
        for key, item in current.items():
            prior = previous.get(key)
            if prior is None and _available(item):
                changes.append({"field": item.get("field"), "change_type": "new_claim", "previous_value": None, "current_value": item.get("value")})
            elif prior is not None and _available(prior) and _available(item) and _canonical(prior.get("value")) != _canonical(item.get("value")):
                changes.append({"field": item.get("field"), "change_type": "changed_value", "previous_value": prior.get("value"), "current_value": item.get("value")})
            elif prior is not None and not _available(prior) and _available(item):
                changes.append({"field": item.get("field"), "change_type": "claim_became_available", "previous_value": None, "current_value": item.get("value")})
            merged[key] = copy.deepcopy(dict(item))

        for key, prior in previous.items():
            if key not in current and _available(prior):
                changes.append({"field": prior.get("field"), "change_type": "claim_removed", "previous_value": prior.get("value"), "current_value": None})
                merged.pop(key, None)

    ordered_claims = tuple(merged[key] for key in sorted(merged))
    ordered_evidence = tuple(evidence[key] for key in sorted(evidence))
    changes.sort(key=lambda item: (str(item.get("field")), str(item.get("change_type")), _canonical(item)))
    return RefreshResult(ordered_claims, ordered_evidence, tuple(changes), failed and bool(previous))


def refresh_json(previous: Mapping[str, Any], current: Mapping[str, Any], *, refresh_state: str = "available") -> dict[str, Any]:
    """Refresh two envelope-like dictionaries without mutating either input."""

    result = refresh_claims(
        previous.get("claims", ()),
        previous.get("evidence", ()),
        current.get("claims", ()),
        current.get("evidence", ()),
        refresh_state=refresh_state,
    )
    return result.to_dict()


__all__ = ["RefreshResult", "claim_key", "refresh_claims", "refresh_json"]
