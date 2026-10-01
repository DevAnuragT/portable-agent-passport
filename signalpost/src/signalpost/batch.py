"""JSONL input/output runner with no silent drops."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from .adapters import OfficialDataAdapter, RequestBudget, bind_request_budget
from .agent import SignalpostAgent
from .models import Availability, Claim, CompanyInput, CompanyProfile, ErrorRecord, OperationMetrics, OutputEnvelope, ProfileSection, RunMetadata


def read_jsonl(path: Union[str, Path]) -> List[CompanyInput]:
    source = Path(path)
    inputs: List[CompanyInput] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            inputs.append(CompanyInput.from_json(json.loads(line)))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSONL input on line {line_number}: {exc}") from exc
    if not inputs:
        raise ValueError("input JSONL contains no companies")
    numbers = [item.organisation_number for item in inputs]
    if len(numbers) != len(set(numbers)):
        raise ValueError("input JSONL contains duplicate organisation numbers")
    return inputs


def read_output_jsonl(path: Union[str, Path]) -> Dict[str, Mapping[str, Any]]:
    """Read and validate a prior result file for refresh comparison or resume."""

    records: Dict[str, Mapping[str, Any]] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            envelope = OutputEnvelope.from_dict(raw)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid prior output on line {line_number}: {exc}") from exc
        if envelope.organisation_number in records:
            raise ValueError(f"prior output contains duplicate organisation number {envelope.organisation_number}")
        records[envelope.organisation_number] = raw
    return records


def _failed_envelope(company: CompanyInput, run_id: str, timestamp: str, error: Exception, requests: int = 0) -> OutputEnvelope:
    state = Availability.FAILED
    claim = Claim("claim-run-failure", "profile", None, state)
    section = ProfileSection(state, (claim.id,))
    profile = CompanyProfile(section, section, section, section, section, section, section)
    return OutputEnvelope(
        company.organisation_number,
        state,
        RunMetadata(run_id, timestamp, timestamp, state),
        profile,
        (claim,),
        (),
        (),
        (),
        (ErrorRecord("agent_exception", f"{type(error).__name__}: {error}"),),
        OperationMetrics(requests, 0, 0.0),
    )


def run_batch(
    inputs: Iterable[CompanyInput],
    adapter: OfficialDataAdapter,
    output: Optional[Union[str, Path]] = None,
    previous: Optional[Mapping[str, Mapping[str, Any]]] = None,
    resume: bool = False,
    workers: int = 1,
    request_budget: Optional[Union[int, RequestBudget]] = None,
) -> List[OutputEnvelope]:
    companies = list(inputs)
    if not companies:
        raise ValueError("batch contains no companies")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")
    if isinstance(request_budget, RequestBudget):
        budget = request_budget
    else:
        # Even an unlimited run gets a shared counter.  This lets the batch
        # repair per-company metrics when a decorated adapter has mutable
        # compatibility counters, without imposing a limit.
        budget = RequestBudget(request_budget)
    budget_managed = False
    if budget is not None:
        setter = getattr(adapter, "set_request_budget", None)
        if setter is not None:
            setter(budget)
            budget_managed = True
        else:
            # WebsiteEnabledAdapter intentionally remains a thin decorator;
            # propagate the budget to its registry adapter when present.
            base = getattr(adapter, "base", None)
            base_setter = getattr(base, "set_request_budget", None)
            if base_setter is not None:
                base_setter(budget)
                budget_managed = True
    fetcher = getattr(adapter, "fetcher", None)
    if fetcher is not None:
        bind_request_budget(fetcher, budget)
        budget_managed = True
    batch_key = "\n".join(item.organisation_number for item in companies)
    run_id = hashlib.sha256((getattr(adapter, "revision", "adapter") + "\n" + batch_key).encode()).hexdigest()[:16]
    timestamp = getattr(adapter, "reference_time", "2026-01-01T00:00:00Z")

    def execute(index: int, company: CompanyInput) -> tuple[int, OutputEnvelope]:
        # Each task gets its own agent, while the adapter and (when live) its
        # RequestBudget are shared.  The adapter's request counter is
        # thread-local, so operations remain attributable to this company.
        agent = SignalpostAgent(adapter)
        request_start = budget.consumed_by_current_thread() if budget_managed else 0
        try:
            prior = (previous or {}).get(company.organisation_number)
            if resume and prior is not None:
                envelope = OutputEnvelope.from_dict(prior)
            else:
                envelope = agent.research(company, run_id, prior)
                if budget_managed:
                    request_count = budget.consumed_by_current_thread() - request_start
                    envelope = replace(envelope, operations=replace(envelope.operations, requests=request_count))
            return index, envelope
        except Exception as exc:  # one terminal envelope per valid input is non-negotiable
            request_count = budget.consumed_by_current_thread() - request_start if budget_managed else int(getattr(adapter, "last_request_count", 0))
            return index, _failed_envelope(company, run_id, timestamp, exc, request_count)

    envelopes: List[Optional[OutputEnvelope]] = [None] * len(companies)
    with ThreadPoolExecutor(max_workers=min(workers, len(companies))) as executor:
        futures = [executor.submit(execute, index, company) for index, company in enumerate(companies)]
        for future in as_completed(futures):
            index, envelope = future.result()
            envelopes[index] = envelope
    # Every submitted task returns either its normal or failure envelope.  Keep
    # this assertion local so a future implementation cannot silently drop a
    # row while preserving the public list return type.
    completed = [envelope for envelope in envelopes if envelope is not None]
    if len(completed) != len(companies):
        raise RuntimeError("batch did not produce one terminal envelope per input")
    final_envelopes = completed
    aggregate_requests = sum(envelope.operations.requests for envelope in final_envelopes)
    setattr(run_batch, "last_request_count", aggregate_requests)
    try:
        setattr(adapter, "aggregate_request_count", aggregate_requests)
    except (AttributeError, TypeError):
        pass
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".signalpost-", suffix=".jsonl", dir=str(destination.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for envelope in final_envelopes:
                    handle.write(envelope.json() + "\n")
            os.replace(temporary, destination)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    return final_envelopes
