"""Local contract smoke runner and reproducible JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .adapters import BulkBrregAdapter, FixtureBrregAdapter, LiveBrregAdapter, LocalJsonlAdapter
from .batch import read_jsonl, run_batch
from .models import Availability, CompanyInput
from .website import WebsiteEnabledAdapter, WebsiteFetcher


def _check_digit(prefix: str) -> Optional[str]:
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    remainder = sum(int(digit) * weight for digit, weight in zip(prefix, weights)) % 11
    digit = 11 - remainder
    if digit == 10:
        return None
    return "0" if digit == 11 else str(digit)


def generated_inputs(count: int) -> List[CompanyInput]:
    if count < 1:
        raise ValueError("generated smoke count must be positive")
    values = []
    candidate = 10000000
    while len(values) < count:
        prefix = str(candidate)
        digit = _check_digit(prefix)
        candidate += 1
        if digit is None:
            continue
        number = prefix + digit
        values.append(CompanyInput(number, request_id="generated-smoke-%03d" % (len(values) + 1)))
    return values


def percentile(values: List[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def build_report(envelopes, expected_count: int, source: str) -> dict:
    states = {state.value: sum(1 for item in envelopes if item.state is state) for state in Availability}
    wrong_company = 0
    evidence_invalid = 0
    for envelope in envelopes:
        legal = next((claim for claim in envelope.claims if claim.field == "legal_identity" and claim.availability is Availability.AVAILABLE), None)
        if legal is not None and (not isinstance(legal.value, dict) or legal.value.get("organisation_number") != envelope.organisation_number):
            wrong_company += 1
        evidence_ids = {item.id for item in envelope.evidence}
        if any(not set(claim.evidence_ids) <= evidence_ids for claim in envelope.claims):
            evidence_invalid += 1
    runtimes = [item.operations.runtime_ms for item in envelopes]
    requests = sum(item.operations.requests for item in envelopes)
    failures = [item.organisation_number for item in envelopes if item.state is Availability.FAILED]
    return {
        "report_type": "signalpost_local_contract_smoke",
        "official_score_claimed": False,
        "source": source,
        "expected_inputs": expected_count,
        "terminal_envelopes": len(envelopes),
        "exactly_one_terminal_envelope_per_input": len(envelopes) == expected_count,
        "states": states,
        "failures": failures,
        "wrong_company_publications": wrong_company,
        "evidence_linkage_errors": evidence_invalid,
        "requests": requests,
        "third_party_cost_usd": sum(item.operations.third_party_cost_usd for item in envelopes),
        "runtime_ms_total": sum(runtimes),
        "runtime_ms_p50": percentile(runtimes, 0.50),
        "runtime_ms_p95": percentile(runtimes, 0.95),
        "checks_passed": len(envelopes) == expected_count and not failures and wrong_company == 0 and evidence_invalid == 0,
    }


def _default_fixture() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "brreg_fixture.json"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local Signalpost smoke test")
    parser.add_argument("--input", help="JSONL input; omit to generate deterministic inputs")
    parser.add_argument("--generated-count", type=int, default=100)
    parser.add_argument("--include-fixture-companies", action="store_true", help="Include the two bundled known-company fixture records")
    parser.add_argument("--report", required=True)
    parser.add_argument("--adapter", choices=("fixture", "local-jsonl", "bulk", "live"), default="fixture")
    parser.add_argument("--source", help="Fixture JSON or local JSONL adapter source")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        if args.input:
            inputs = read_jsonl(args.input)
            source = args.input
        else:
            if args.include_fixture_companies:
                if args.generated_count < 2:
                    raise ValueError("--generated-count must be at least 2 with --include-fixture-companies")
                inputs = [CompanyInput("923609016", request_id="fixture-known-1"), CompanyInput("974760673", request_id="fixture-known-2")] + generated_inputs(args.generated_count - 2)
                source = "two bundled fixture companies plus generated deterministic organisation numbers"
            else:
                inputs = generated_inputs(args.generated_count)
                source = "generated deterministic organisation numbers"
        if args.adapter == "fixture":
            adapter = FixtureBrregAdapter(args.source or _default_fixture())
        elif args.adapter == "local-jsonl":
            if not args.source:
                raise ValueError("--source is required for --adapter local-jsonl")
            adapter = LocalJsonlAdapter(args.source)
        elif args.adapter == "bulk":
            if not args.source:
                raise ValueError("--source is required for --adapter bulk")
            adapter = BulkBrregAdapter(args.source)
        else:
            adapter = WebsiteEnabledAdapter(LiveBrregAdapter(args.timeout), WebsiteFetcher(args.timeout))
        envelopes = run_batch(inputs, adapter)
        report = build_report(envelopes, len(inputs), source)
        destination = Path(args.report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("signalpost-smoke: " + json.dumps(report, sort_keys=True), file=sys.stderr)
        return 0 if report["checks_passed"] else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("signalpost-smoke: error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
