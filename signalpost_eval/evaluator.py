"""Deterministic, standard-library-only Signalpost evaluation.

The evaluator consumes two JSONL streams: the requested companies and the terminal
envelopes produced for them.  It never imports ``signalpost``.  Every non-empty
input line is paired by position with exactly one output line; a count mismatch is
reported as a schema failure rather than silently dropping records.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union


STATES = ("available", "not_available", "blocked", "not_applicable", "ambiguous", "failed")
PROFILE_SECTIONS = (
    "legal_identity",
    "annual_accounts",
    "leadership",
    "workplaces",
    "group_links",
    "official_website",
    "hiring_and_activity",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T[^ ]+Z$")


class EvaluationError(ValueError):
    """Raised by the strict public JSONL reader for malformed JSON."""


def read_jsonl(path: Union[str, Path]) -> List[Any]:
    """Read non-empty JSONL records, raising on malformed JSON.

    ``evaluate_files`` uses a lossless internal reader so malformed lines are also
    represented in its machine-readable report.
    """

    records, errors = _read_jsonl(Path(path))
    if errors:
        first = errors[0]
        raise EvaluationError(f"invalid JSONL on line {first['line']}: {first['message']}")
    return records


def _read_jsonl(path: Path) -> Tuple[List[Any], List[Dict[str, Any]]]:
    records: List[Any] = []
    errors: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvaluationError(f"cannot read {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            records.append(None)
            errors.append({"line": line_number, "message": str(exc)})
    return records, errors


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalise_org(value: Any) -> Optional[str]:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace(" ", "").replace(".", "")
    return text if re.fullmatch(r"\d{9}", text) else None


def _valid_org(value: Any) -> bool:
    number = _normalise_org(value)
    if number is None:
        return False
    remainder = sum(int(digit) * weight for digit, weight in zip(number[:8], (3, 2, 7, 6, 5, 4, 3, 2))) % 11
    check_digit = 11 - remainder
    if check_digit == 11:
        check_digit = 0
    return check_digit != 10 and check_digit == int(number[-1])


def _issue(index: int, code: str, message: str, category: str, severity: str = "error") -> Dict[str, Any]:
    return {"index": index, "code": code, "message": message, "category": category, "severity": severity}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _validate_envelope(envelope: Any, requested_org: Optional[str], index: int) -> List[Dict[str, Any]]:
    """Validate one envelope and return stable, human-readable findings."""

    issues: List[Dict[str, Any]] = []
    if not isinstance(envelope, Mapping):
        return [_issue(index, "envelope_not_object", "terminal envelope must be a JSON object", "schema")]

    required = {"organisation_number", "state", "run", "profile", "claims", "evidence", "snapshots", "changes", "errors", "operations"}
    missing = sorted(required - set(envelope))
    if missing:
        issues.append(_issue(index, "missing_envelope_fields", ", ".join(missing), "schema"))

    org = _normalise_org(envelope.get("organisation_number"))
    if not _valid_org(envelope.get("organisation_number")):
        issues.append(_issue(index, "invalid_envelope_organisation_number", "envelope organisation_number is not a valid Norwegian organisation number", "schema"))
    if requested_org is not None and org != requested_org:
        issues.append(_issue(index, "envelope_identity_mismatch", "envelope organisation_number does not match its input", "identity"))

    state = envelope.get("state")
    if state not in STATES:
        issues.append(_issue(index, "invalid_state", "state must be one of the documented terminal states", "schema"))

    run = envelope.get("run")
    if not isinstance(run, Mapping):
        issues.append(_issue(index, "invalid_run", "run must be an object", "schema"))
    else:
        for name in ("run_id", "started_at", "completed_at", "terminal_status"):
            if name not in run:
                issues.append(_issue(index, "missing_run_field", f"run.{name} is required", "schema"))
        for name in ("started_at", "completed_at"):
            if name in run and (not isinstance(run[name], str) or not UTC_TIMESTAMP.fullmatch(run[name])):
                issues.append(_issue(index, "invalid_timestamp", f"run.{name} must be a UTC timestamp ending in Z", "schema"))
        if state in STATES and run.get("terminal_status") != state:
            issues.append(_issue(index, "terminal_status_mismatch", "run.terminal_status must equal state", "schema"))

    claims = envelope.get("claims")
    evidence = envelope.get("evidence")
    snapshots = envelope.get("snapshots")
    for name, value in (("claims", claims), ("evidence", evidence), ("snapshots", snapshots), ("changes", envelope.get("changes")), ("errors", envelope.get("errors"))):
        if not isinstance(value, list):
            issues.append(_issue(index, f"invalid_{name}", f"{name} must be an array", "schema"))

    claim_ids: set[str] = set()
    evidence_ids: set[str] = set()
    snapshot_ids: set[str] = set()
    if isinstance(snapshots, list):
        for item in snapshots:
            if not isinstance(item, Mapping):
                issues.append(_issue(index, "invalid_snapshot", "snapshot must be an object", "schema"))
                continue
            sid = item.get("id")
            if not isinstance(sid, str) or not sid:
                issues.append(_issue(index, "invalid_snapshot_id", "snapshot id is required", "schema"))
            elif sid in snapshot_ids:
                issues.append(_issue(index, "duplicate_snapshot_id", sid, "schema"))
            else:
                snapshot_ids.add(sid)
            _validate_source(item, index, issues, snapshot=True)

    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, Mapping):
                issues.append(_issue(index, "invalid_evidence", "evidence must be an object", "schema"))
                continue
            eid = item.get("id")
            if not isinstance(eid, str) or not eid:
                issues.append(_issue(index, "invalid_evidence_id", "evidence id is required", "schema"))
            elif eid in evidence_ids:
                issues.append(_issue(index, "duplicate_evidence_id", eid, "schema"))
            else:
                evidence_ids.add(eid)
            _validate_source(item, index, issues)
            span = item.get("span")
            if not isinstance(span, Mapping) or not isinstance(span.get("locator"), str) or not span.get("locator") or not isinstance(span.get("quote"), str) or not span.get("quote"):
                issues.append(_issue(index, "invalid_evidence_span", "evidence requires a non-empty span locator and quote", "evidence"))
            if item.get("snapshot_id") is not None and item.get("snapshot_id") not in snapshot_ids:
                issues.append(_issue(index, "missing_snapshot_reference", f"evidence {eid!r} references an unknown snapshot", "evidence"))

    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, Mapping):
                issues.append(_issue(index, "invalid_claim", "claim must be an object", "schema"))
                continue
            cid = claim.get("id")
            if not isinstance(cid, str) or not cid:
                issues.append(_issue(index, "invalid_claim_id", "claim id is required", "schema"))
            elif cid in claim_ids:
                issues.append(_issue(index, "duplicate_claim_id", cid, "schema"))
            else:
                claim_ids.add(cid)
            if not isinstance(claim.get("field"), str) or not claim.get("field"):
                issues.append(_issue(index, "invalid_claim_field", "claim field is required", "schema"))
            availability = claim.get("availability")
            if availability not in STATES:
                issues.append(_issue(index, "invalid_claim_availability", f"claim {cid!r} has an unknown availability", "schema"))
            refs = claim.get("evidence_ids")
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                issues.append(_issue(index, "invalid_claim_evidence_ids", f"claim {cid!r} evidence_ids must be an array of strings", "schema"))
                refs = []
            if availability == "available" and not refs:
                issues.append(_issue(index, "available_claim_without_evidence", f"claim {cid!r} is available without evidence", "evidence"))
            if availability != "available" and claim.get("value") is not None:
                issues.append(_issue(index, "unavailable_claim_has_value", f"claim {cid!r} publishes a value while unavailable", "availability"))
            for ref in refs:
                if ref not in evidence_ids:
                    issues.append(_issue(index, "missing_claim_evidence", f"claim {cid!r} references unknown evidence {ref!r}", "evidence"))
            confidence = claim.get("confidence")
            if confidence is not None and (not _is_number(confidence) or not 0 <= confidence <= 1):
                issues.append(_issue(index, "invalid_confidence", f"claim {cid!r} confidence must be between 0 and 1", "schema"))

            if availability == "available" and isinstance(refs, list):
                evidence_by_id = {item.get("id"): item for item in evidence if isinstance(item, Mapping)} if isinstance(evidence, list) else {}
                value_text = _canonical(claim.get("value"))
                if isinstance(claim.get("value"), str):
                    value_text = claim["value"]
                supported = any(value_text and value_text in str(evidence_by_id.get(ref, {}).get("span", {}).get("quote", "")) for ref in refs)
                if not supported:
                    issues.append(_issue(index, "unsupported_claim", f"claim {cid!r} is not supported by its evidence span", "evidence"))

    profile = envelope.get("profile")
    if not isinstance(profile, Mapping):
        issues.append(_issue(index, "invalid_profile", "profile must be an object", "schema"))
    else:
        for section_name in PROFILE_SECTIONS:
            section = profile.get(section_name)
            if not isinstance(section, Mapping):
                issues.append(_issue(index, "missing_profile_section", f"profile.{section_name} is required", "schema"))
                continue
            if section.get("availability") not in STATES:
                issues.append(_issue(index, "invalid_profile_availability", f"profile.{section_name}.availability is invalid", "schema"))
            refs = section.get("claim_ids")
            if not isinstance(refs, list) or not all(ref in claim_ids for ref in refs):
                issues.append(_issue(index, "missing_profile_claim", f"profile.{section_name} references an unknown claim", "schema"))

    operations = envelope.get("operations")
    if not isinstance(operations, Mapping):
        issues.append(_issue(index, "invalid_operations", "operations must be an object", "schema"))
    else:
        for name in ("requests", "runtime_ms", "third_party_cost_usd"):
            if name not in operations or not _is_number(operations.get(name)) or operations.get(name) < 0:
                issues.append(_issue(index, "invalid_operation_metric", f"operations.{name} must be a non-negative number", "schema"))

    if isinstance(envelope.get("changes"), list):
        for change in envelope["changes"]:
            if not isinstance(change, Mapping) or not isinstance(change.get("field"), str) or not isinstance(change.get("change_type"), str):
                issues.append(_issue(index, "invalid_change", "each change requires field and change_type", "refresh"))
    return issues


def _validate_source(item: Mapping[str, Any], index: int, issues: List[Dict[str, Any]], snapshot: bool = False) -> None:
    if not isinstance(item.get("source_url"), str) or not (item["source_url"].startswith("http://") or item["source_url"].startswith("https://")):
        issues.append(_issue(index, "invalid_source_url", "source_url must be an HTTP(S) URL", "evidence"))
    if not isinstance(item.get("retrieved_at"), str) or not UTC_TIMESTAMP.fullmatch(item.get("retrieved_at", "")):
        issues.append(_issue(index, "invalid_retrieved_at", "retrieved_at must be a UTC timestamp ending in Z", "evidence"))
    if not isinstance(item.get("content_hash"), str) or not HEX64.fullmatch(item.get("content_hash", "")):
        issues.append(_issue(index, "invalid_content_hash", "content_hash must be a lowercase SHA-256 digest", "evidence"))
    if snapshot and not isinstance(item.get("status_code"), (int, type(None))):
        issues.append(_issue(index, "invalid_snapshot_status", "snapshot status_code must be an integer or null", "schema"))


def _input_org(row: Any) -> Optional[str]:
    if isinstance(row, str):
        return _normalise_org(row) if _valid_org(row) else None
    if isinstance(row, Mapping):
        return _normalise_org(row.get("organisation_number")) if _valid_org(row.get("organisation_number")) else None
    return None


def _percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 4) if denominator else 0.0


def _distribution(values: Iterable[float]) -> Dict[str, float]:
    numbers = sorted(float(value) for value in values)
    if not numbers:
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "p95": 0}
    p95_index = min(len(numbers) - 1, max(0, math.ceil(len(numbers) * 0.95) - 1))
    return {"count": len(numbers), "min": numbers[0], "max": numbers[-1], "mean": round(sum(numbers) / len(numbers), 4), "median": float(median(numbers)), "p95": numbers[p95_index]}


def evaluate_batch(inputs: Sequence[Any], envelopes: Sequence[Any], input_errors: Optional[Sequence[Mapping[str, Any]]] = None, output_errors: Optional[Sequence[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    """Return a machine-readable evaluation report for parsed JSONL records."""

    findings: List[Dict[str, Any]] = []
    for parse_error in input_errors or ():
        findings.append(_issue(int(parse_error.get("line", 0)), "invalid_input_json", str(parse_error.get("message", "invalid JSON")), "schema"))
    for parse_error in output_errors or ():
        findings.append(_issue(int(parse_error.get("line", 0)), "invalid_output_json", str(parse_error.get("message", "invalid JSON")), "schema"))

    input_orgs = [_input_org(row) for row in inputs]
    for index, org in enumerate(input_orgs, 1):
        if org is None:
            findings.append(_issue(index, "invalid_input", "input must contain a valid Norwegian organisation_number", "schema"))

    input_count = len(inputs)
    output_count = len(envelopes)
    if output_count != input_count:
        findings.append(_issue(0, "envelope_count_mismatch", f"expected exactly one envelope per input ({input_count}), got {output_count}", "schema"))

    paired = min(input_count, output_count)
    valid_envelopes = 0
    identity_matching = 0
    identity_mismatches = 0
    identity_missing = 0
    state_counts: Counter[str] = Counter()
    claim_availability: Counter[str] = Counter()
    profile_availability: Counter[str] = Counter()
    all_requests: List[float] = []
    all_runtime: List[float] = []
    all_cost: List[float] = []
    change_types: Counter[str] = Counter()
    envelope_results: List[Dict[str, Any]] = []
    unsupported_claim_count = 0
    evidence_count = 0
    linked_evidence_count = 0
    available_claim_count = 0

    for position in range(paired):
        index = position + 1
        envelope = envelopes[position]
        org = input_orgs[position]
        before = len(findings)
        envelope_issues = _validate_envelope(envelope, org, index)
        findings.extend(envelope_issues)
        if not envelope_issues:
            valid_envelopes += 1
        envelope_results.append({"index": index, "organisation_number": org, "valid": not envelope_issues, "issue_count": len(envelope_issues), "issue_codes": [item["code"] for item in envelope_issues]})
        if not isinstance(envelope, Mapping):
            continue
        state = envelope.get("state")
        if state in STATES:
            state_counts[state] += 1
        claims = envelope.get("claims") if isinstance(envelope.get("claims"), list) else []
        evidence = envelope.get("evidence") if isinstance(envelope.get("evidence"), list) else []
        evidence_count += len(evidence)
        available_claim_count += sum(1 for claim in claims if isinstance(claim, Mapping) and claim.get("availability") == "available")
        for claim in claims:
            if isinstance(claim, Mapping) and claim.get("availability") in STATES:
                claim_availability[claim["availability"]] += 1
                refs = claim.get("evidence_ids") if isinstance(claim.get("evidence_ids"), list) else []
                linked_evidence_count += sum(1 for ref in refs if any(isinstance(item, Mapping) and item.get("id") == ref for item in evidence))
        profile = envelope.get("profile") if isinstance(envelope.get("profile"), Mapping) else {}
        for name in PROFILE_SECTIONS:
            section = profile.get(name)
            if isinstance(section, Mapping) and section.get("availability") in STATES:
                profile_availability[section["availability"]] += 1
        ops = envelope.get("operations")
        if isinstance(ops, Mapping):
            if _is_number(ops.get("requests")) and ops["requests"] >= 0:
                all_requests.append(float(ops["requests"]))
            if _is_number(ops.get("runtime_ms")) and ops["runtime_ms"] >= 0:
                all_runtime.append(float(ops["runtime_ms"]))
            if _is_number(ops.get("third_party_cost_usd")) and ops["third_party_cost_usd"] >= 0:
                all_cost.append(float(ops["third_party_cost_usd"]))
        changes = envelope.get("changes") if isinstance(envelope.get("changes"), list) else []
        for change in changes:
            if isinstance(change, Mapping) and isinstance(change.get("change_type"), str):
                change_types[change["change_type"]] += 1

        identity_claims = [claim for claim in claims if isinstance(claim, Mapping) and claim.get("field") == "legal_identity"]
        matching = False
        # An envelope-level organisation mismatch is an identity failure even
        # when the claim list happens to be internally self-consistent.
        mismatch = org is not None and _normalise_org(envelope.get("organisation_number")) != org
        for claim in identity_claims:
            value = claim.get("value")
            claimed_org = value.get("organisation_number") if isinstance(value, Mapping) else None
            if claim.get("availability") == "available" and _normalise_org(claimed_org) != org:
                mismatch = True
                findings.append(_issue(index, "identity_claim_mismatch", "legal_identity claim does not match the requested organisation number", "identity"))
            elif claim.get("availability") == "available" and _normalise_org(claimed_org) == org:
                matching = True
        if matching:
            identity_matching += 1
        if mismatch:
            identity_mismatches += 1
        if not identity_claims:
            identity_missing += 1
            if state == "available":
                findings.append(_issue(index, "missing_identity_claim", "available envelope has no legal_identity claim", "identity"))

        unsupported_codes = {"unsupported_claim", "available_claim_without_evidence", "missing_claim_evidence"}
        unsupported = sum(1 for item in envelope_issues if item["code"] in unsupported_codes)
        unsupported_claim_count += unsupported

    if output_count > input_count:
        for index in range(input_count + 1, output_count + 1):
            findings.append(_issue(index, "extra_envelope", "output contains an envelope without a corresponding input", "schema"))
    if input_count > output_count:
        for index in range(output_count + 1, input_count + 1):
            findings.append(_issue(index, "missing_envelope", "input has no terminal envelope", "schema"))

    # A report is useful even when the submission is bad; ``passed`` is only a
    # local contract result and is not an official Builderr score.
    errors_by_category = Counter(item["category"] for item in findings if item.get("severity") == "error")
    return {
        "report_version": "signalpost-eval/1",
        "passed": not findings,
        "schema": {
            "input_count": input_count,
            "envelope_count": output_count,
            "paired_count": paired,
            "valid_envelope_count": valid_envelopes,
            "invalid_envelope_count": paired - valid_envelopes,
            "missing_envelope_count": max(0, input_count - output_count),
            "extra_envelope_count": max(0, output_count - input_count),
            "one_envelope_per_input": output_count == input_count and not (input_errors or output_errors),
            "error_count": sum(errors_by_category.values()),
            "errors_by_category": dict(sorted(errors_by_category.items())),
        },
        "identity": {
            "requested_count": input_count,
            "matching_count": identity_matching,
            "mismatch_count": identity_mismatches,
            "missing_identity_count": identity_missing,
            "precision_percent": _percent(identity_matching, input_count),
        },
        "evidence": {
            "evidence_count": evidence_count,
            "available_claim_count": available_claim_count,
            "linked_evidence_reference_count": linked_evidence_count,
            "unsupported_claim_count": unsupported_claim_count,
            "span_validity_percent": _percent(max(0, available_claim_count - unsupported_claim_count), available_claim_count),
        },
        "availability": {
            "envelope_states": {state: state_counts.get(state, 0) for state in STATES},
            "claim_states": {state: claim_availability.get(state, 0) for state in STATES},
            "profile_section_states": {state: profile_availability.get(state, 0) for state in STATES},
        },
        "refresh": {
            "change_event_count": sum(change_types.values()),
            "envelopes_with_changes": sum(1 for envelope in envelopes if isinstance(envelope, Mapping) and envelope.get("changes")),
            "change_type_counts": dict(sorted(change_types.items())),
            "snapshot_count": sum(len(envelope.get("snapshots", [])) for envelope in envelopes if isinstance(envelope, Mapping) and isinstance(envelope.get("snapshots"), list)),
        },
        "requests": {
            "total_requests": int(sum(all_requests)) if all(request.is_integer() for request in all_requests) else round(sum(all_requests), 4),
            "per_envelope": _distribution(all_requests),
            "total_cost_usd": round(sum(all_cost), 6),
        },
        "runtime": {
            "runtime_ms": _distribution(all_runtime),
            "cost_usd": _distribution(all_cost),
        },
        "envelopes": envelope_results,
        "findings": findings,
    }


def evaluate_files(input_path: Union[str, Path], output_path: Union[str, Path]) -> Dict[str, Any]:
    """Evaluate JSONL files without network access or agent imports."""

    inputs, input_errors = _read_jsonl(Path(input_path))
    envelopes, output_errors = _read_jsonl(Path(output_path))
    return evaluate_batch(inputs, envelopes, input_errors, output_errors)


def report_digest(report: Mapping[str, Any]) -> str:
    """Return a stable digest useful for smoke-test provenance."""

    return hashlib.sha256(_canonical(report).encode("utf-8")).hexdigest()
