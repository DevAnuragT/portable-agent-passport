"""Deterministic Signalpost research core for official and permitted web facts."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .adapters import BRREG_ENDPOINTS, MODULES, ModuleResult, OfficialDataAdapter
from .models import (
    Availability,
    ChangeEvent,
    Claim,
    CompanyInput,
    CompanyProfile,
    ErrorRecord,
    Evidence,
    EvidenceSpan,
    OperationMetrics,
    OutputEnvelope,
    ProfileSection,
    RunMetadata,
    SourceSnapshot,
    content_hash,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _nonempty(value: Any) -> bool:
    """Whether a source observation contains a publishable value."""

    if value is None:
        return False
    if isinstance(value, (str, bytes, Mapping, Sequence)):
        return bool(value)
    return True


def _raw_value_span(raw: Any, target: Any, path: str = "") -> Optional[tuple[str, str]]:
    """Find an exact value in a decoded source body.

    Normalisers are allowed to reshape registry responses.  An exact recursive
    match is therefore preferred over pretending the reshaped value was a raw
    response span.
    """

    if type(raw) is type(target) and raw == target:
        return path or "/", target if isinstance(target, str) else _canonical(target)
    if isinstance(raw, Mapping):
        for key, item in raw.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            found = _raw_value_span(item, target, f"{path}/{escaped}")
            if found:
                return found
    elif isinstance(raw, list):
        for index, item in enumerate(raw):
            found = _raw_value_span(item, target, f"{path}/{index}")
            if found:
                return found
    return None


def _normalise_identity(body: Any) -> dict[str, Any]:
    source = _as_dict(body)
    form = source.get("organisasjonsform")
    industry = source.get("naeringskode1")
    return {
        "organisation_number": source.get("organisasjonsnummer"),
        "name": source.get("navn"),
        "legal_form": form.get("kode") if isinstance(form, dict) else form,
        "employees": source.get("antallAnsatte"),
        "website": source.get("hjemmeside"),
        "industry": industry,
        "business_address": source.get("forretningsadresse"),
        "postal_address": source.get("postadresse"),
        "latest_submitted_accounts": source.get("sisteInnsendteAarsregnskap"),
        "bankrupt": source.get("konkurs"),
        "liquidating": source.get("underAvvikling"),
    }


def _normalise_accounts(body: Any) -> dict[str, Any]:
    rows = body if isinstance(body, list) else []
    records = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        result = item.get("resultatregnskapResultat") or {}
        operating = result.get("driftsresultat") or {}
        income = operating.get("driftsinntekter") or {}
        equity_debt = item.get("egenkapitalGjeld") or {}
        equity = equity_debt.get("egenkapital") or {}
        debt = equity_debt.get("gjeldOversikt") or {}
        records.append({
            "record_id": item.get("id"),
            "account_type": item.get("regnskapstype"),
            "period": item.get("regnskapsperiode"),
            "currency": item.get("valuta"),
            "revenue": income.get("sumDriftsinntekter"),
            "operating_result": operating.get("driftsresultat"),
            "profit_before_tax": result.get("ordinaertResultatFoerSkattekostnad"),
            "annual_result": result.get("aarsresultat"),
            "assets": (item.get("eiendeler") or {}).get("sumEiendeler"),
            "equity": equity.get("sumEgenkapital"),
            "debt": debt.get("sumGjeld"),
        })
    return {"records": records}


def _normalise_roles(body: Any) -> dict[str, Any]:
    roles = []
    for group in (_as_dict(body).get("rollegrupper") or []):
        if not isinstance(group, dict):
            continue
        for item in group.get("roller") or []:
            person = _as_dict(item.get("person"))
            name = _as_dict(person.get("navn"))
            entity = _as_dict(item.get("enhet"))
            display_name = " ".join(filter(None, [name.get("fornavn"), name.get("mellomnavn"), name.get("etternavn")])) or entity.get("navn")
            role_type = _as_dict(item.get("type"))
            group_type = _as_dict(group.get("type"))
            roles.append({
                "name": display_name,
                "organisation_number": entity.get("organisasjonsnummer"),
                "role_code": role_type.get("kode"),
                "role": role_type.get("beskrivelse"),
                "group_code": group_type.get("kode"),
                "group": group_type.get("beskrivelse"),
                "last_changed": group.get("sistEndret"),
                "inactive": bool(item.get("avregistrert")),
            })
    return {"roles": roles}


def _normalise_workplaces(body: Any) -> dict[str, Any]:
    rows = _as_dict(_as_dict(body).get("_embedded")).get("underenheter") or _as_dict(body).get("underenheter") or []
    locations = []
    for item in rows:
        if isinstance(item, dict):
            locations.append({
                "organisation_number": item.get("organisasjonsnummer"),
                "name": item.get("navn"),
                "address": item.get("beliggenhetsadresse") or item.get("postadresse"),
                "industry": item.get("naeringskode1"),
                "employees": item.get("antallAnsatte"),
            })
    return {"locations": locations}


def _normalise_history(body: Any) -> dict[str, Any]:
    years = sorted({str(year) for year in (body if isinstance(body, list) else []) if str(year).isdigit()})
    return {"years": years}


NORMALISERS = {
    "legal_identity": _normalise_identity,
    "annual_accounts": _normalise_accounts,
    "annual_account_history": _normalise_history,
    "leadership": _normalise_roles,
    "workplaces": _normalise_workplaces,
    "group_links": lambda body: body if isinstance(body, (dict, list)) else {},
}

SECTION_BY_MODULE = {
    "legal_identity": "legal_identity",
    "annual_accounts": "annual_accounts",
    "annual_account_history": "annual_accounts",
    "leadership": "leadership",
    "workplaces": "workplaces",
    "group_links": "group_links",
}

WEBSITE_CLAIM_MODULES = ("hiring_activity", "public_activity")


class SignalpostAgent:
    """Research one company through an injected official-data adapter."""

    def __init__(self, adapter: OfficialDataAdapter):
        self.adapter = adapter

    def research(self, company: CompanyInput, run_id: Optional[str] = None, previous: Optional[Mapping[str, Any]] = None) -> OutputEnvelope:
        started_clock = time.monotonic()
        run_id = run_id or hashlib.sha256((self.adapter.revision + company.organisation_number).encode()).hexdigest()[:16]
        results = dict(self.adapter.fetch_company(company.organisation_number))
        request_count = int(getattr(self.adapter, "last_request_count", len(results)))
        evidence: list[Evidence] = []
        snapshots: list[SourceSnapshot] = []
        claims: list[Claim] = []
        errors: list[ErrorRecord] = []
        section_claims: Dict[str, list[str]] = {name: [] for name in ("legal_identity", "annual_accounts", "leadership", "workplaces", "group_links", "official_website", "hiring_and_activity")}

        identity = results.get("legal_identity") or self._missing_result("legal_identity", company.organisation_number)
        results["legal_identity"] = identity
        identity_ok = identity.available
        identity_value: Optional[dict[str, Any]] = None
        if identity_ok:
            identity_value = _normalise_identity(identity.body)
            if identity_value.get("organisation_number") != company.organisation_number:
                identity_ok = False
                errors.append(ErrorRecord("identity_mismatch", "official response organisation number did not match the request", "legal_identity"))
        if identity_ok:
            claim = self._claim("legal_identity", identity_value, identity, evidence, confidence=1.0)
            claims.append(claim)
            section_claims["legal_identity"].append(claim.id)
            website = identity_value.get("website")
            # Registry association is retained as a candidate, but the profile's
            # official_website section is populated only after static-site corroboration.
            if website:
                candidate = self._claim("registry_website_candidate", website, identity, evidence, confidence=0.95)
                claims.append(candidate)
        else:
            if identity.error == "organisation not present in fixture":
                errors.append(ErrorRecord("not_in_source", identity.error, "legal_identity"))
            elif identity.error:
                errors.append(ErrorRecord("identity_source_error", identity.error, "legal_identity"))
            unavailable = Availability.AMBIGUOUS if identity.available else self._status(identity)
            identity_claim = self._unavailable_claim("legal_identity", unavailable, identity, evidence)
            claims.append(identity_claim)
            section_claims["legal_identity"].append(identity_claim.id)
            website_claim = self._unavailable_claim("official_website", unavailable, identity, evidence)
            claims.append(website_claim)
            section_claims["official_website"].append(website_claim.id)

        if identity_ok:
            website_result = results.get("website_profile")
            website_candidates = self._website_candidates(website_result)
            # Only canonical URL can populate official_website.  A page title
            # or description is useful enrichment, never a website URL.
            official_candidate = next(
                (candidate for candidate in website_candidates if candidate["field"] == "canonical_url" and isinstance(candidate["value"], str)),
                None,
            )
            if official_candidate is not None:
                website_claim = self._website_candidate_claim("official_website", official_candidate, website_result, evidence, confidence=0.95)
                claims.append(website_claim)
                section_claims["official_website"].append(website_claim.id)
            elif website_result is not None and website_result.available and isinstance(website_result.body, dict) and website_result.body.get("verified"):
                website_claim = self._derived_website_url_claim(website_result, evidence)
                claims.append(website_claim)
                section_claims["official_website"].append(website_claim.id)
            else:
                status = self._website_status(website_result, bool(website_candidates))
                website_claim = self._unavailable_claim("official_website", status, website_result, evidence)
                claims.append(website_claim)
                section_claims["official_website"].append(website_claim.id)

        # An identity failure is a hard publication gate: retain source errors but do not
        # publish facts from modules that cannot be attributed to the requested entity.
        for module in ("annual_accounts", "annual_account_history", "leadership", "workplaces", "group_links"):
            result = results.get(module) or self._missing_result(module, company.organisation_number)
            results[module] = result
            if identity_ok and result.available:
                value = NORMALISERS[module](result.body)
                claim = self._claim(module, value, result, evidence, confidence=0.99 if module == "annual_accounts" else 0.95)
                claims.append(claim)
                section_claims[SECTION_BY_MODULE[module]].append(claim.id)
            else:
                status = self._status(result) if identity_ok else Availability.AMBIGUOUS
                # Missing means module was intentionally not requested by this
                # run.  Do not turn selective-module execution into false
                # source errors; real HTTP/API failures still surface.
                if (
                    result.error
                    and identity_ok
                    and result.error != "module not present in adapter"
                    and result.status_code not in (404, 410)
                ):
                    errors.append(ErrorRecord("module_source_error", result.error, module))
                claim = self._unavailable_claim(module, status, result, evidence)
                claims.append(claim)
                section_claims[SECTION_BY_MODULE[module]].append(claim.id)

        website_result = results.get("website_profile")
        website_candidates = self._website_candidates(website_result)
        website_verified = bool(website_candidates)
        for module in WEBSITE_CLAIM_MODULES:
            result = results.get(module)
            observations = self._website_observations(module, result, website_candidates) if website_verified else ()
            if observations:
                for observation in observations:
                    claim = self._website_candidate_claim(module, observation, result, evidence, confidence=0.85)
                    claims.append(claim)
                    section_claims["hiring_and_activity"].append(claim.id)
            else:
                status = self._website_status(result, website_verified)
                claim = self._unavailable_claim(module, status, result, evidence)
                claims.append(claim)
                section_claims["hiring_and_activity"].append(claim.id)

        activity = self._unavailable_claim("hiring_and_activity", Availability.NOT_AVAILABLE, None, evidence)
        if not section_claims["hiring_and_activity"]:
            claims.append(activity)
            section_claims["hiring_and_activity"].append(activity.id)

        for module, result in results.items():
            if result.content_sha256 is None:
                continue
            snapshot_id = self._stable_id("snapshot", module, result.content_sha256)
            snapshots.append(SourceSnapshot(snapshot_id, result.source_url, result.retrieved_at, result.content_sha256, result.status_code, result.source_class, result.error))

        state = Availability.AVAILABLE if identity_ok else (Availability.AMBIGUOUS if identity.available else self._status(identity))
        reference_time = getattr(self.adapter, "reference_time", identity.retrieved_at)
        profile = CompanyProfile(
            self._section(section_claims, "legal_identity", claims),
            self._section(section_claims, "annual_accounts", claims),
            self._section(section_claims, "leadership", claims),
            self._section(section_claims, "workplaces", claims),
            self._section(section_claims, "group_links", claims),
            self._section(section_claims, "official_website", claims),
            self._section(section_claims, "hiring_and_activity", claims),
        )
        runtime_ms = 0 if getattr(self.adapter, "deterministic", False) else int((time.monotonic() - started_clock) * 1000)
        run = RunMetadata(run_id, reference_time, reference_time, state)
        changes = self._changes_since(previous, claims)
        return OutputEnvelope(
            company.organisation_number,
            state,
            run,
            profile,
            claims,
            evidence,
            snapshots,
            changes,
            errors,
            OperationMetrics(request_count, runtime_ms, 0.0),
        )

    @staticmethod
    def _stable_id(org: str, module: str, digest: str) -> str:
        return "sp-" + hashlib.sha256(f"{org}:{module}:{digest}".encode()).hexdigest()[:20]

    def _claim(self, field: str, value: Any, result: ModuleResult, evidence: list[Evidence], confidence: float) -> Claim:
        eid = self._stable_id(result.source_url, field, result.content_sha256 or content_hash(result.body))
        snapshot_id = self._stable_id("snapshot", result.module, result.content_sha256 or content_hash(result.body))
        digest = result.content_sha256 or content_hash(result.body)
        raw_span = _raw_value_span(result.body, value)
        if raw_span:
            locator, quote = raw_span
            span = EvidenceSpan(locator, quote)
            extraction_method = "deterministic_json"
        else:
            # A normalised value is useful, but it is not a verbatim quote from
            # the response.  Keep that distinction explicit in both fields.
            span = EvidenceSpan(
                f"derived:{field} from JSON normalization of /",
                f"Derived value (not a verbatim source quote): {_canonical(value)}",
                kind="derived",
            )
            extraction_method = "derived_json_normalization"
        source_name = "Brønnøysundregistrene" if result.source_class.startswith("official_registry") else "Registry-listed company website"
        evidence.append(Evidence(eid, result.source_url, source_name, result.source_class, result.retrieved_at, digest, span, extraction_method=extraction_method, reporting_period=result.reporting_period, snapshot_id=snapshot_id))
        return Claim("claim-" + eid[3:], field, value, Availability.AVAILABLE, (eid,), confidence)

    def _availability_claim(self, field: str, value: Any, result: ModuleResult, evidence: list[Evidence], confidence: float) -> Claim:
        if value is None or value == "":
            return self._unavailable_claim(field, Availability.NOT_AVAILABLE, result, evidence)
        return self._claim(field, value, result, evidence, confidence)

    def _unavailable_claim(self, field: str, status: Availability, result: Optional[ModuleResult], evidence: list[Evidence]) -> Claim:
        # An unavailable result has no claim value.  In particular, do not add
        # an invented error sentence as a quote against the response hash.
        return Claim("claim-" + hashlib.sha256(field.encode()).hexdigest()[:20], field, None, status)

    @staticmethod
    def _website_candidates(result: Optional[ModuleResult]) -> tuple[Mapping[str, Any], ...]:
        """Return only parser candidates tied to this exact website snapshot."""

        if result is None or not result.available or not isinstance(result.body, dict) or not result.body.get("verified"):
            return ()
        raw_candidates = result.body.get("candidate_claims")
        if not isinstance(raw_candidates, list) or not result.content_sha256:
            return ()
        valid: list[Mapping[str, Any]] = []
        for candidate in raw_candidates:
            if not isinstance(candidate, Mapping):
                continue
            candidate_hash = candidate.get("content_sha256", candidate.get("content_hash"))
            if candidate_hash != result.content_sha256:
                continue
            if candidate.get("source_url") != result.source_url:
                continue
            if candidate.get("retrieved_at") != result.retrieved_at:
                continue
            if not isinstance(candidate.get("evidence_locator"), str) or not candidate.get("evidence_locator"):
                continue
            if not isinstance(candidate.get("evidence_quote"), str) or not candidate.get("evidence_quote"):
                continue
            if not _nonempty(candidate.get("value")):
                continue
            valid.append(candidate)
        return tuple(valid)

    @staticmethod
    def _website_status(result: Optional[ModuleResult], website_verified: bool) -> Availability:
        if result is None:
            return Availability.NOT_AVAILABLE
        if result.available:
            # A successful page without parser candidates is a checked source,
            # not evidence for an observation and not an identity ambiguity.
            return Availability.NOT_AVAILABLE
        return SignalpostAgent._status(result)

    @staticmethod
    def _website_observations(module: str, result: Optional[ModuleResult], candidates: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
        if result is None or not result.available or not isinstance(result.body, dict):
            return ()
        if module == "hiring_activity":
            candidate_fields = {"jobs": "jobs_links", "careers": "careers_links"}
            source_values = {
                value
                for values in (result.body.get("jobs", ()), result.body.get("careers", ()))
                if isinstance(values, (list, tuple))
                for value in values
                if isinstance(value, str)
            }
        else:
            candidate_fields = {"news": "news_links"}
            source_values = {
                value
                for value in (result.body.get("news", ()))
                if isinstance(value, str)
            } if isinstance(result.body.get("news", ()), (list, tuple)) else set()
        observations: list[Mapping[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            if candidate.get("field") not in candidate_fields.values():
                continue
            values = candidate.get("value")
            values = values if isinstance(values, (list, tuple)) else (values,)
            quote = str(candidate.get("evidence_quote", ""))
            for value in values:
                if not isinstance(value, str) or not value or value not in source_values or value not in quote:
                    continue
                key = (str(candidate.get("id", "")), value)
                if key in seen:
                    continue
                seen.add(key)
                observations.append({**candidate, "value": value})
        return tuple(observations)

    def _website_candidate_claim(self, field: str, candidate: Mapping[str, Any], result: ModuleResult, evidence: list[Evidence], confidence: float) -> Claim:
        digest = str(candidate["content_sha256"])
        identity = _canonical({"field": field, "candidate": candidate.get("id"), "value": candidate.get("value"), "hash": digest})
        eid = self._stable_id(result.source_url, field, hashlib.sha256(identity.encode()).hexdigest())
        snapshot_id = self._stable_id("snapshot", result.module, digest)
        evidence.append(
            Evidence(
                eid,
                str(candidate["source_url"]),
                "Registry-listed company website",
                result.source_class,
                str(candidate["retrieved_at"]),
                digest,
                EvidenceSpan(str(candidate["evidence_locator"]), str(candidate["evidence_quote"]), kind="html"),
                extraction_method="website_candidate",
                snapshot_id=snapshot_id,
            ))
        return Claim("claim-" + eid[3:], field, candidate["value"], Availability.AVAILABLE, (eid,), confidence)

    def _derived_website_url_claim(self, result: ModuleResult, evidence: list[Evidence]) -> Claim:
        digest = result.content_sha256 or content_hash(result.body)
        eid = self._stable_id(result.source_url, "official_website", digest)
        snapshot_id = self._stable_id("snapshot", result.module, digest)
        evidence.append(
            Evidence(
                eid,
                result.source_url,
                "Registry-listed company website",
                result.source_class,
                result.retrieved_at,
                digest,
                EvidenceSpan(
                    "derived:verified_fetch_url",
                    f"{result.source_url} — derived from fetched registry-listed URL after exact-company identity verification",
                    kind="derived",
                ),
                extraction_method="verified_fetch_url",
                snapshot_id=snapshot_id,
            )
        )
        return Claim("claim-" + eid[3:], "official_website", result.source_url, Availability.AVAILABLE, (eid,), 0.95)

    @staticmethod
    def _missing_result(module: str, org: str) -> ModuleResult:
        return ModuleResult(module, BRREG_ENDPOINTS[module].format(org=org), "2026-01-01T00:00:00Z", 404, None, "module not present in adapter", content_hash(None))

    @staticmethod
    def _status(result: ModuleResult) -> Availability:
        if result.status_code in (401, 403, 429):
            return Availability.BLOCKED
        if result.status_code in (404, 410):
            return Availability.NOT_AVAILABLE
        return Availability.FAILED

    @staticmethod
    def _section(section_claims: Mapping[str, list[str]], name: str, claims: Sequence[Claim]) -> ProfileSection:
        claim_ids = section_claims[name]
        selected = next((claim for claim in claims if claim.id in claim_ids and claim.availability is Availability.AVAILABLE), None)
        selected = selected or next((claim for claim in claims if claim.id in claim_ids), None)
        return ProfileSection(selected.availability if selected else Availability.NOT_AVAILABLE, tuple(claim_ids))

    @staticmethod
    def _changes_since(previous: Optional[Mapping[str, Any]], claims: Sequence[Claim]) -> tuple[ChangeEvent, ...]:
        if not previous:
            return ()
        old_claims = {str(item.get("field")): item for item in previous.get("claims", ()) if isinstance(item, Mapping) and item.get("field")}
        events: list[ChangeEvent] = []
        for claim in claims:
            old = old_claims.get(claim.field)
            old_status = str(old.get("availability")) if old else None
            old_value = old.get("value") if old else None
            if old is None and claim.availability is Availability.AVAILABLE:
                events.append(ChangeEvent(claim.field, "new_claim", None, claim.value))
            elif old is not None and (old_status != claim.availability.value or _canonical(old_value) != _canonical(claim.value)):
                change_type = "claim_retracted" if claim.availability is not Availability.AVAILABLE else "changed_value"
                events.append(ChangeEvent(claim.field, change_type, old_value, claim.value))
        current_fields = {claim.field for claim in claims}
        for field, old in old_claims.items():
            if field not in current_fields and str(old.get("availability")) == Availability.AVAILABLE.value:
                events.append(ChangeEvent(field, "claim_removed", old.get("value"), None))
        return tuple(sorted(events, key=lambda event: event.field))
