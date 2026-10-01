"""Official-data adapter interfaces and deterministic/local implementations."""

from __future__ import annotations

import hashlib
import csv
import gzip
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol, Union

from .models import content_hash
from .validation import validate_organisation_number


BRREG_ENDPOINTS = {
    "legal_identity": "https://data.brreg.no/enhetsregisteret/api/enheter/{org}",
    "leadership": "https://data.brreg.no/enhetsregisteret/api/enheter/{org}/roller",
    "workplaces": "https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={org}&size=1000",
    "group_links": "https://data.brreg.no/enhetsregisteret/api/konsernstruktur/{org}",
    "annual_accounts": "https://data.brreg.no/regnskapsregisteret/regnskap/{org}",
    "annual_account_history": "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{org}/aar",
}

MODULES = tuple(BRREG_ENDPOINTS)
WEBSITE_MODULES = ("website_robots", "website_sitemap", "website_profile", "hiring_activity", "public_activity")
WEBSITE_ENDPOINTS = {
    "website_robots": "{website}/robots.txt",
    "website_sitemap": "{website}/sitemap.xml",
    "website_profile": "{website}/",
    "hiring_activity": "{website}/",
    "public_activity": "{website}/",
}


class RequestBudget:
    """Thread-safe allowance for network requests in one batch run.

    Acquiring an allowance is deliberately separate from performing a request:
    callers can refuse the request before constructing/opening any network
    connection once the shared allowance is exhausted.
    """

    def __init__(self, limit: Optional[int]):
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
            raise ValueError("request budget must be a non-negative integer")
        self.limit = limit
        self._remaining = limit
        self._consumed = 0
        self._thread_consumed: Dict[int, int] = {}
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        with self._lock:
            if self._remaining is not None and self._remaining <= 0:
                return False
            if self._remaining is not None:
                self._remaining -= 1
            self._consumed += 1
            thread_id = threading.get_ident()
            self._thread_consumed[thread_id] = self._thread_consumed.get(thread_id, 0) + 1
            return True

    @property
    def remaining(self) -> Optional[int]:
        with self._lock:
            return self._remaining

    @property
    def consumed(self) -> int:
        with self._lock:
            return self._consumed

    def consumed_by_current_thread(self) -> int:
        with self._lock:
            return self._thread_consumed.get(threading.get_ident(), 0)


def bind_request_budget(fetcher: Any, budget: Optional[RequestBudget]) -> None:
    """Guard a compatible website fetcher without widening its URL policy.

    ``WebsiteFetcher`` is kept in its own module for compatibility.  Its two
    network entry points are wrapped here so a batch can share one allowance
    across registry and website calls without changing the fetcher's public
    API.  The original fetch operation is serialized because that fetcher
    intentionally keeps request-budget counters as instance state.
    """

    if not hasattr(fetcher, "fetch_url") or not hasattr(fetcher, "fetch"):
        return
    state = getattr(fetcher, "_signalpost_budget_state", None)
    if state is not None:
        state["budget"] = budget
        return
    original_fetch = fetcher.fetch
    original_fetch_url = fetcher.fetch_url
    lock = threading.Lock()
    state = {"budget": budget}

    def guarded_fetch(*args: Any, **kwargs: Any) -> Any:
        with lock:
            return original_fetch(*args, **kwargs)

    def guarded_fetch_url(url: str) -> Any:
        active = state["budget"]
        if active is not None and not active.acquire():
            from .website import FetchResponse

            return FetchResponse(b"", 429, utc_now(), url)
        return original_fetch_url(url)

    setattr(fetcher, "fetch", guarded_fetch)
    setattr(fetcher, "fetch_url", guarded_fetch_url)
    setattr(fetcher, "_signalpost_budget_state", state)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ModuleResult:
    module: str
    source_url: str
    retrieved_at: str
    status_code: Optional[int]
    body: Any = None
    error: Optional[str] = None
    content_sha256: Optional[str] = None
    reporting_period: Optional[str] = None
    source_class: str = "official_registry"

    @property
    def available(self) -> bool:
        return self.status_code == 200 and self.error is None


class OfficialDataAdapter(Protocol):
    """Small interface consumed by the core agent; network is never used directly there."""

    revision: str
    reference_time: str

    def fetch_company(self, organisation_number: str) -> Mapping[str, ModuleResult]:
        ...


def _fixture_result(module: str, org: str, raw: Any, defaults: Mapping[str, Any]) -> ModuleResult:
    fallback = BRREG_ENDPOINTS.get(module, "https://example.invalid/" + module).format(org=org)
    endpoint = str(raw.get("source_url") or fallback) if isinstance(raw, Mapping) else fallback
    retrieved_at = str(raw.get("retrieved_at") or defaults.get("retrieved_at") or "2026-01-01T00:00:00Z") if isinstance(raw, Mapping) else str(defaults.get("retrieved_at") or "2026-01-01T00:00:00Z")
    status = int(raw.get("status_code", raw.get("status", 200))) if isinstance(raw, Mapping) else 200
    body = raw.get("body") if isinstance(raw, Mapping) and "body" in raw else raw
    error = raw.get("error") if isinstance(raw, Mapping) else None
    digest = str(raw.get("content_sha256") or content_hash(body)) if isinstance(raw, Mapping) else content_hash(body)
    source_class = str(raw.get("source_class") or "official_registry") if isinstance(raw, Mapping) else "official_registry"
    return ModuleResult(module, endpoint, retrieved_at, status, body, error, digest, raw.get("reporting_period") if isinstance(raw, Mapping) else None, source_class)


class FixtureBrregAdapter:
    """Loads a saved BRREG-shaped manifest and performs no network calls."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._defaults = payload.get("defaults", {})
        records = payload.get("companies", payload.get("records", []))
        self._records: Dict[str, Mapping[str, Any]] = {}
        for record in records:
            org = str(record.get("organisation_number", ""))
            if org:
                self._records[org] = record
        self.revision = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.reference_time = str(self._defaults.get("retrieved_at") or "2026-01-01T00:00:00Z")
        self.deterministic = True
        self.last_request_count = 0

    def fetch_company(self, organisation_number: str) -> Mapping[str, ModuleResult]:
        record = self._records.get(organisation_number)
        if record is None:
            return {
                "legal_identity": ModuleResult(
                    "legal_identity",
                    BRREG_ENDPOINTS["legal_identity"].format(org=organisation_number),
                    self.reference_time,
                    404,
                    None,
                    "organisation not present in fixture",
                    content_hash(None),
                )
            }
        modules = record.get("modules", record.get("evidence", {}))
        supported = MODULES + WEBSITE_MODULES
        return {module: _fixture_result(module, organisation_number, modules.get(module), self._defaults) for module in supported if module in modules}


class LocalJsonlAdapter(FixtureBrregAdapter):
    """Same deterministic adapter for a local JSONL corpus (one company per line)."""

    def __init__(self, path: Union[str, Path]):
        source = Path(path)
        records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.path = source
        self._defaults = {"retrieved_at": "2026-01-01T00:00:00Z"}
        self._records = {str(record["organisation_number"]): record for record in records}
        self.revision = hashlib.sha256(source.read_bytes()).hexdigest()
        self.reference_time = self._defaults["retrieved_at"]
        self.deterministic = True
        self.last_request_count = 0


class BulkBrregAdapter:
    """Offline loader for BRREG bulk CSV/CSV.GZ identity snapshots."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self._records: Dict[str, Mapping[str, Any]] = {}
        opener = gzip.open if self.path.suffix.casefold() == ".gz" else open
        with opener(self.path, "rt", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(8192)
            handle.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
            for row in csv.DictReader(handle, dialect=dialect):
                org = self._first(row, "organisasjonsnummer", "Organisasjonsnummer")
                try:
                    org = validate_organisation_number(org)
                except ValueError:
                    continue
                self._records[org] = dict(row)
        self.revision = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.reference_time = "2026-01-01T00:00:00Z"
        self.deterministic = True
        self.last_request_count = 0

    @staticmethod
    def _first(row: Mapping[str, str], *names: str) -> str:
        for name in names:
            value = row.get(name)
            if value not in (None, ""):
                return str(value)
        return ""

    def fetch_company(self, organisation_number: str) -> Mapping[str, ModuleResult]:
        row = self._records.get(organisation_number)
        url = BRREG_ENDPOINTS["legal_identity"].format(org=organisation_number)
        if row is None:
            return {"legal_identity": ModuleResult("legal_identity", url, self.reference_time, 404, None, "organisation not present in bulk snapshot", content_hash(None), source_class="official_registry_bulk")}
        employees = self._first(row, "antallAnsatte", "Antall ansatte")
        industry_code = self._first(row, "naeringskode1.kode", "Næringskode1.kode")
        industry_name = self._first(row, "naeringskode1.beskrivelse", "Næringskode1.beskrivelse")
        body = {
            "organisasjonsnummer": organisation_number,
            "navn": self._first(row, "navn", "Navn"),
            "organisasjonsform": {"kode": self._first(row, "organisasjonsform.kode", "Organisasjonsform.kode")},
            "antallAnsatte": int(employees) if employees.isdigit() else None,
            "hjemmeside": self._first(row, "hjemmeside", "Hjemmeside") or None,
            "naeringskode1": {"kode": industry_code, "beskrivelse": industry_name} if industry_code or industry_name else None,
            "sisteInnsendteAarsregnskap": self._first(row, "sisteInnsendteAarsregnskap", "Siste innsendte årsregnskap") or None,
            "konkurs": self._first(row, "konkurs", "Konkurs").casefold() == "true",
            "underAvvikling": self._first(row, "underAvvikling", "Under avvikling").casefold() == "true",
            "forretningsadresse": {"kommune": self._first(row, "forretningsadresse.kommune", "Forretningsadresse.kommune") or None},
        }
        return {"legal_identity": ModuleResult("legal_identity", url, self.reference_time, 200, body, None, content_hash(row), source_class="official_registry_bulk")}


class LiveBrregAdapter:
    """Minimal BRREG HTTP adapter, isolated behind ``OfficialDataAdapter``.

    It only constructs fixed official endpoints; callers cannot supply arbitrary URLs.
    Tests and the default CLI never select this adapter.
    """

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        opener: Optional[Callable[..., Any]] = None,
        modules: Optional[Iterable[str]] = None,
        request_budget: Optional[Union[int, RequestBudget]] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen
        if isinstance(modules, str):
            selected = tuple(part.strip() for part in modules.split(",") if part.strip())
        else:
            selected = tuple(MODULES if modules is None else modules)
        unknown = sorted(set(selected) - set(MODULES))
        if not selected:
            raise ValueError("live adapter requires at least one module")
        if unknown:
            raise ValueError("unsupported live module(s): " + ", ".join(unknown))
        if len(set(selected)) != len(selected):
            raise ValueError("live modules must be unique")
        self.modules = selected
        if request_budget is not None and not isinstance(request_budget, RequestBudget):
            request_budget = RequestBudget(request_budget)
        self.request_budget = request_budget
        self._counts = threading.local()
        self.aggregate_request_count = 0
        self.revision = "brreg-live-v1" if self.modules == MODULES else "brreg-live-v1:" + ",".join(self.modules)
        self.reference_time = utc_now()

    @property
    def last_request_count(self) -> int:
        """Requests made by the current company task (safe under batch threads)."""

        return int(getattr(self._counts, "value", self.aggregate_request_count))

    def set_request_budget(self, budget: Optional[Union[int, RequestBudget]]) -> None:
        if budget is not None and not isinstance(budget, RequestBudget):
            budget = RequestBudget(budget)
        self.request_budget = budget

    def _set_request_count(self, value: int) -> None:
        self._counts.value = value

    def fetch_company(self, organisation_number: str) -> Mapping[str, ModuleResult]:
        results: Dict[str, ModuleResult] = {}
        self._set_request_count(0)
        for module in self.modules:
            template = BRREG_ENDPOINTS[module]
            url = template.format(org=organisation_number)
            retrieved_at = utc_now()
            if self.request_budget is not None and not self.request_budget.acquire():
                results[module] = ModuleResult(
                    module,
                    url,
                    retrieved_at,
                    429,
                    None,
                    "request budget exhausted",
                    content_hash(None),
                )
                continue
            self._set_request_count(self.last_request_count + 1)
            try:
                request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Signalpost/0.1"})
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    raw_bytes = response.read()
                    status = int(getattr(response, "status", 200))
                    body = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else None
                    results[module] = ModuleResult(module, url, retrieved_at, status, body, None, hashlib.sha256(raw_bytes).hexdigest())
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                category = "blocked by source" if status in (401, 403, 429) else "source returned HTTP error"
                results[module] = ModuleResult(module, url, retrieved_at, status, None, f"{category}: {status}", content_hash(None))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                results[module] = ModuleResult(module, url, retrieved_at, None, None, f"{type(exc).__name__}: {exc}", content_hash(None))
        return results
