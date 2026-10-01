"""Deterministic enrichment for a registry-listed company website.

This module intentionally has a small boundary.  It accepts HTTP(S) URLs only,
does not execute JavaScript, and never treats a page as belonging to a company
until the supplied legal identity can be found on the page.  The fetch function
is injectable so all parsing and identity tests can run without a network.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import gzip
import io
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.robotparser
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .adapters import ModuleResult, utc_now


# This is deliberately a small, conservative list.  Without a dependency on a
# public-suffix database, these common two-label suffixes prevent the most
# important co.uk/com.au style false positives.  Unknown suffixes use the last
# two labels, which is preferable to allowing arbitrary cross-domain links.
_TWO_LABEL_SUFFIXES = frozenset(
    {
        "ac.uk",
        "co.uk",
        "gov.uk",
        "org.uk",
        "com.au",
        "net.au",
        "org.au",
        "co.nz",
        "com.br",
        "com.cn",
        "com.hk",
        "com.sg",
        "co.jp",
        "co.kr",
        "co.za",
        "com.tr",
        "com.mx",
    }
)
_DATE_RE = re.compile(r"\b20\d{2}[-/.]\d{1,2}(?:[-/.]\d{1,2})?\b")
_EMAIL_RE = re.compile(r"\b[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?[0-9][0-9 ()./-]{6,}[0-9])(?!\w)")
_JOB_WORDS = ("career", "careers", "karriere", "job", "jobs", "stilling", "vacancy", "vacancies", "work-with-us")
_NEWS_WORDS = ("news", "nyhet", "nyheter", "press", "aktuelt", "insight", "blog")


def _is_public_host(host: str) -> bool:
    """Reject URL hosts that can directly name a local/private destination.

    DNS is deliberately not resolved here: resolution would make parsing URLs a
    network operation and would make injected-opener tests non-deterministic.
    The real transport still needs the deployment's normal DNS-rebinding
    protection, but literal IPs, legacy IPv4 spellings and local hostnames are
    rejected before the opener is called.
    """

    host = host.rstrip(".").casefold()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    try:
        # inet_aton recognises legacy forms such as 127.1 and 2130706433.
        return ipaddress.ip_address(socket.inet_aton(host)).is_global
    except (OSError, ValueError):
        pass
    # Single-label names are normally resolved by local search domains.
    if "." not in host:
        return False
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", ascii_host))


def _normalise_url(value: str) -> Optional[str]:
    """Return a safe, fragment-free HTTP(S) URL, or ``None``.

    A scheme is required rather than guessed.  Guessing turns text such as a
    user-provided host name into an implicit network permission.
    """

    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname
        if parsed.scheme.lower() not in ("http", "https") or not host:
            return None
        if not _is_public_host(host):
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        # Accessing port catches malformed values such as :abc.
        if parsed.port is not None and not 0 < parsed.port < 65536:
            return None
    except (TypeError, ValueError):
        return None
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc, path, parsed.query, ""))


def _registry_url(value: str) -> Optional[str]:
    """Normalise registry host values without guessing arbitrary user URLs."""

    text = str(value or "").strip()
    if text and "://" not in text and not text.startswith("/"):
        text = "https://" + text
    return _normalise_url(text)


def is_allowed_url(value: str) -> bool:
    """Whether *value* is an absolute URL allowed by the website boundary."""

    return _normalise_url(value) is not None


def _host(value: str) -> str:
    try:
        host = urllib.parse.urlsplit(value).hostname or ""
        return host.rstrip(".").encode("idna").decode("ascii").lower()
    except (AttributeError, UnicodeError, ValueError):
        return ""


def registered_domain(value: str) -> str:
    """Return a deterministic registrable-domain approximation for a URL/host."""

    host = _host(value) if "://" in value else value.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = [label for label in host.split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    suffix = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix in _TWO_LABEL_SUFFIXES else suffix


def same_registered_domain(left: str, right: str) -> bool:
    """Allow a URL only when it shares the registry domain with the root URL."""

    return bool(_normalise_url(left) and _normalise_url(right) and registered_domain(left) == registered_domain(right))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _identity_text(value: str) -> str:
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _compact_identity(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def _org_digits(value: str) -> str:
    return re.sub(r"[^0-9]", "", str(value or ""))


def _flatten_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def _address_tokens(value: Any) -> set[str]:
    return {token for token in re.findall(r"[\w]{4,}", _identity_text(_flatten_text(value))) if not token.isdigit()}


@dataclass(frozen=True)
class FetchResponse:
    """Minimal response accepted from an injected website fetcher."""

    body: bytes
    status_code: int = 200
    retrieved_at: str = ""
    final_url: Optional[str] = None


@dataclass(frozen=True)
class CandidateClaim:
    """A deterministic, not-yet-published website claim."""

    id: str
    field: str
    value: Any
    source_url: str
    retrieved_at: str
    content_sha256: str
    evidence_quote: str
    evidence_locator: str = "html"

    @property
    def content_hash(self) -> str:
        """Alias matching the core evidence model's terminology."""

        return self.content_sha256

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "field": self.field,
            "value": _json_value(self.value),
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
            "content_hash": self.content_sha256,
            "evidence_quote": self.evidence_quote,
            "evidence_locator": self.evidence_locator,
        }


@dataclass(frozen=True)
class WebsiteEnrichment:
    """Static-page extraction, with claims empty when identity is unproven."""

    source_url: str
    retrieved_at: str
    content_sha256: str
    identity_proven: bool
    abstained: bool
    reason: Optional[str]
    claims: Sequence[CandidateClaim] = ()
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    links: Mapping[str, Sequence[str]] = None  # type: ignore[assignment]
    organization: Optional[Mapping[str, Any]] = None
    jobs: Sequence[Mapping[str, Any]] = ()
    activity: Sequence[Mapping[str, Any]] = ()
    contact: Optional[Mapping[str, Any]] = None
    address: Any = None

    def __post_init__(self) -> None:
        if self.links is None:
            object.__setattr__(self, "links", {})

    @property
    def candidate_claims(self) -> Sequence[CandidateClaim]:
        return self.claims

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
            "identity_proven": self.identity_proven,
            "verified": self.identity_proven,
            "abstained": self.abstained,
            "reason": self.reason,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "description": self.description,
            "organization": _json_value(self.organization),
            "contact": _json_value(self.contact),
            "address": _json_value(self.address),
            "jobs": [_json_value(item) for item in self.jobs],
            "activity": [_json_value(item) for item in self.activity],
            "links": {key: list(value) for key, value in (self.links or {}).items()},
            "careers_links": list((self.links or {}).get("careers", ())),
            "jobs_links": list((self.links or {}).get("jobs", ())),
            "news_links": list((self.links or {}).get("news", ())),
            "candidate_claims": [claim.to_dict() for claim in self.claims],
        }


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: List[str] = []
        self.text: List[str] = []
        self.address: List[str] = []
        self.links: List[Dict[str, str]] = []
        self.meta: Dict[str, str] = {}
        self.canonical: Optional[str] = None
        self.json_ld: List[Tuple[Any, str]] = []
        self._title = False
        self._address = False
        self._skip = 0
        self._script_type = ""
        self._script: List[str] = []
        self._link: Optional[Dict[str, str]] = None

    def handle_starttag(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        values = {key.lower(): (value or "") for key, value in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "title":
            self._title = True
        elif tag == "address":
            self._address = True
        elif tag == "meta":
            key = (values.get("name") or values.get("property") or "").casefold()
            if key and values.get("content") and key not in self.meta:
                self.meta[key] = _clean(values["content"])
        elif tag == "link" and "canonical" in values.get("rel", "").casefold().split():
            self.canonical = values.get("href") or self.canonical
        elif tag == "a" and values.get("href"):
            self._link = {"href": values["href"], "text": ""}
        if tag == "script":
            self._script_type = values.get("type", "").casefold()
            self._script = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._title = False
        elif tag == "address":
            self._address = False
        elif tag == "a" and self._link is not None:
            self.links.append(self._link)
            self._link = None
        elif tag == "script":
            raw = "".join(self._script).strip()
            if raw and "ld+json" in self._script_type:
                try:
                    value = json.loads(raw)
                    values = value if isinstance(value, list) else [value]
                    self.json_ld.extend((item, raw) for item in values)
                except (TypeError, ValueError):
                    pass
            self._script = []
            self._script_type = ""
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data: str) -> None:
        if self._script_type:
            self._script.append(data)
        if self._skip:
            return
        clean = _clean(data)
        if not clean:
            return
        if self._title:
            self.title.append(clean)
        if self._address:
            self.address.append(clean)
        if self._link is not None:
            self._link["text"] = _clean(self._link["text"] + " " + clean)
        self.text.append(clean)


def _jsonld_objects(values: Iterable[Tuple[Any, str]]) -> Iterable[Tuple[Mapping[str, Any], str]]:
    for value, raw in values:
        queue = value if isinstance(value, list) else [value]
        while queue:
            item = queue.pop(0)
            if not isinstance(item, Mapping):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
            yield item, raw


def _types(item: Mapping[str, Any]) -> List[str]:
    value = item.get("@type", [])
    return [str(part).casefold() for part in (value if isinstance(value, list) else [value])]


def _absolute_link(page_url: str, href: str) -> Optional[str]:
    candidate = _normalise_url(urllib.parse.urljoin(page_url, html_lib.unescape(href)))
    return candidate if candidate and same_registered_domain(candidate, page_url) else None


def _make_claim(field: str, value: Any, quote: str, source_url: str, retrieved_at: str, digest: str, locator: str) -> CandidateClaim:
    quote = _clean(quote)[:1000]
    # The observation time is metadata, not claim identity.  A byte-identical
    # page replay therefore keeps the same claim id on a later refresh.
    identity = _stable_json({"field": field, "value": value, "source_url": source_url, "content_sha256": digest, "quote": quote, "locator": locator})
    return CandidateClaim(hashlib.sha256(identity.encode("utf-8")).hexdigest(), field, value, source_url, retrieved_at, digest, quote, locator)


def parse_static_html(
    html: Union[str, bytes],
    page_url: str,
    organisation_number: str,
    legal_name: Optional[str] = None,
    retrieved_at: Optional[str] = None,
    registered_address: Any = None,
    registry_domain_proof: bool = False,
) -> WebsiteEnrichment:
    """Parse one static document and produce claims only after identity proof."""

    url = _normalise_url(page_url)
    if not url:
        raise ValueError("page_url must be an absolute HTTP(S) URL")
    raw = html if isinstance(html, bytes) else html.encode("utf-8")
    text_html = raw.decode("utf-8", "replace")
    timestamp = retrieved_at or utc_now()
    digest = _sha256(raw)
    parser = _PageParser()
    parser.feed(text_html)
    visible_text = " ".join(parser.text)
    identity_name = _identity_text(legal_name or "")
    identity_number = _org_digits(organisation_number)
    text_identity = _identity_text(visible_text)
    organization: Optional[Mapping[str, Any]] = None
    organization_raw = ""
    jobs_structured: List[Mapping[str, Any]] = []
    news_structured: List[Mapping[str, Any]] = []
    for item, raw_json in _jsonld_objects(parser.json_ld):
        kinds = _types(item)
        if "organization" in kinds and organization is None:
            organization, organization_raw = item, raw_json
        if "jobposting" in kinds:
            jobs_structured.append(dict(item))
        if any(kind in kinds for kind in ("newsarticle", "article", "blogposting")):
            news_structured.append(dict(item))

    org_json = _stable_json(organization) if organization else ""
    number_proof = bool(identity_number and identity_number in _org_digits(org_json + " " + visible_text))
    name_proof = bool(identity_name and _compact_identity(identity_name) in _compact_identity(org_json + " " + visible_text))
    # Name alone is unsafe: unrelated group/sister companies often print the
    # same legal name.  Require organisation number in source content.
    page_address_text = " ".join(parser.address)
    if organization and organization.get("address"):
        page_address_text += " " + _flatten_text(organization.get("address"))
    address_overlap = _address_tokens(registered_address) & _address_tokens(page_address_text)
    address_proof = len(address_overlap) >= 2
    # Strong secondary proof follows Builderr's playbook: legal-name match plus
    # matching registered address.  Name alone remains unsafe.
    identity_proven = number_proof or (name_proof and (address_proof or registry_domain_proof))

    canonical = _absolute_link(url, parser.canonical) if parser.canonical else None
    title = _clean(" ".join(parser.title)) or None
    description = parser.meta.get("description") or parser.meta.get("og:description")
    contact: Dict[str, Any] = {}
    address: Any = None
    if organization:
        for key in ("email", "telephone", "phone"):
            if organization.get(key):
                contact[key] = organization[key]
        if organization.get("contactPoint"):
            contact["contactPoint"] = organization["contactPoint"]
        address = organization.get("address")
    emails = sorted(set(_EMAIL_RE.findall(visible_text)))
    phones = sorted({value for value in _PHONE_RE.findall(visible_text) if _org_digits(value) != identity_number})
    for link in parser.links:
        href = html_lib.unescape(link.get("href", "")).strip()
        if href.casefold().startswith("mailto:"):
            candidate = href[7:].split("?", 1)[0].strip()
            if candidate and _EMAIL_RE.fullmatch(candidate):
                emails.append(candidate)
        elif href.casefold().startswith("tel:"):
            candidate = href[4:].strip()
            if candidate:
                phones.append(candidate)
    emails = sorted(set(emails))
    phones = sorted(set(phones))
    if emails:
        contact.setdefault("email", emails[0] if len(emails) == 1 else emails)
    if phones:
        contact.setdefault("telephone", phones[0] if len(phones) == 1 else phones)
    if parser.address:
        address = _clean(" ".join(parser.address))

    classified: Dict[str, List[str]] = {"careers": [], "jobs": [], "news": []}
    for link in parser.links:
        absolute = _absolute_link(url, link.get("href", ""))
        if not absolute:
            continue
        label = _clean(link.get("text", ""))
        haystack = (absolute + " " + label).casefold()
        category = "jobs" if any(word in haystack for word in _JOB_WORDS) else "news" if any(word in haystack for word in _NEWS_WORDS) else None
        if category:
            classified[category].append(absolute)
            if category == "jobs" and any(word in haystack for word in ("career", "karriere", "work-with-us")):
                classified["careers"].append(absolute)
    for field, values in (("jobs", jobs_structured), ("news", news_structured)):
        for item in values:
            value = str(item.get("url", ""))
            absolute = _absolute_link(url, value)
            if absolute:
                classified[field].append(absolute)
    links = {key: sorted(set(values)) for key, values in classified.items()}

    claims: List[CandidateClaim] = []
    if identity_proven:
        if organization:
            claims.append(_make_claim("organization", organization, organization_raw or org_json, url, timestamp, digest, "json-ld.Organization"))
        if canonical:
            claims.append(_make_claim("canonical_url", canonical, "canonical: " + canonical, url, timestamp, digest, "link[rel=canonical]"))
        if title:
            claims.append(_make_claim("title", title, title, url, timestamp, digest, "title"))
        if description:
            claims.append(_make_claim("description", description, description, url, timestamp, digest, "meta.description"))
        if contact:
            claims.append(_make_claim("contact", contact, _stable_json(contact), url, timestamp, digest, "contact"))
        if address:
            claims.append(_make_claim("address", address, _stable_json(address) if not isinstance(address, str) else address, url, timestamp, digest, "address"))
        for field in ("careers", "jobs", "news"):
            if links[field]:
                quote = " ; ".join(links[field])
                claims.append(_make_claim(field + "_links", links[field], quote, url, timestamp, digest, "a[href]"))
        claims.sort(key=lambda claim: (claim.field, claim.id))

    return WebsiteEnrichment(
        source_url=url,
        retrieved_at=timestamp,
        content_sha256=digest,
        identity_proven=identity_proven,
        abstained=not identity_proven,
        reason=None if identity_proven else "organisation number or legal-name-plus-registered-address proof was not found",
        claims=tuple(claims),
        canonical_url=canonical,
        title=title,
        description=description,
        links=links,
        organization=organization,
        jobs=tuple(jobs_structured),
        activity=tuple(news_structured),
        contact=contact or None,
        address=address,
    )


class WebsiteEnricher:
    """Fetch and parse one page using an injected, offline-testable fetcher."""

    def __init__(self, fetcher: Optional[Any] = None):
        self.fetcher = fetcher or WebsiteFetcher().fetch_url

    def enrich(
        self,
        website_url: str,
        organisation_number: str,
        legal_name: Optional[str] = None,
        retrieved_at: Optional[str] = None,
        registered_address: Any = None,
    ) -> WebsiteEnrichment:
        url = _normalise_url(website_url)
        if not url:
            raise ValueError("website_url must be an absolute HTTP(S) URL")
        response = _coerce_response(_invoke_fetcher(self.fetcher, url), url)
        timestamp = response.retrieved_at or retrieved_at or utc_now()
        final_url = _normalise_url(response.final_url or url)
        if not final_url or not same_registered_domain(final_url, url):
            return WebsiteEnrichment(url, timestamp, _sha256(response.body), False, True, "redirect left the registry-listed registered domain")
        if response.status_code != 200:
            return WebsiteEnrichment(final_url, timestamp, _sha256(response.body), False, True, "website returned HTTP %s" % response.status_code)
        return parse_static_html(response.body, final_url, organisation_number, legal_name, timestamp, registered_address, registry_domain_proof=True)


def _invoke_fetcher(fetcher: Any, url: str) -> Any:
    """Accept a function or a tiny object implementing ``fetch_url``/``fetch``."""

    if callable(fetcher):
        return fetcher(url)
    method = getattr(fetcher, "fetch_url", None) or getattr(fetcher, "fetch", None)
    if method is None:
        raise TypeError("fetcher must be callable or expose fetch_url(url)")
    return method(url)


def _coerce_response(value: Any, requested_url: str) -> FetchResponse:
    if isinstance(value, FetchResponse):
        return value
    if isinstance(value, Mapping):
        body = value.get("body", value.get("content", b""))
        return FetchResponse(body if isinstance(body, bytes) else str(body).encode("utf-8"), int(value.get("status_code", value.get("status", 200))), str(value.get("retrieved_at", "")), value.get("final_url", value.get("url")))
    if isinstance(value, tuple):
        body = value[0] if value else b""
        return FetchResponse(body if isinstance(body, bytes) else str(body).encode("utf-8"), int(value[2]) if len(value) > 2 else 200, str(value[1]) if len(value) > 1 else "", requested_url)
    body = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return FetchResponse(body, 200, "", requested_url)


def _origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _classify_discovery_url(url: str, label: str = "") -> Optional[str]:
    haystack = (url + " " + label).casefold()
    if any(word in haystack for word in _JOB_WORDS):
        return "jobs"
    if any(word in haystack for word in _NEWS_WORDS):
        return "news"
    return None


def _dated_schema_candidate(
    item: Mapping[str, Any],
    raw_json: str,
    source_url: str,
    retrieved_at: str,
    digest: str,
) -> Optional[Tuple[str, Mapping[str, Any]]]:
    """Return a dated structured candidate with page-level evidence metadata."""

    kinds = _types(item)
    if "jobposting" in kinds:
        category, date_key, title_key, schema_type = "jobs", "datePosted", "title", "JobPosting"
    elif "newsarticle" in kinds:
        category, date_key, title_key, schema_type = "news", "datePublished", "headline", "NewsArticle"
    else:
        return None
    date = _clean(item.get(date_key))
    title = _clean(item.get(title_key) or item.get("name"))
    if not title or not date or not _DATE_RE.search(date):
        return None
    item_url = _clean(item.get("url"))
    if item_url:
        item_url = _absolute_link(source_url, item_url) or ""
        if not item_url:
            return None
    candidate = {
        "type": schema_type,
        "title": title,
        "date": date,
        "data": dict(item),
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "content_sha256": digest,
        "evidence_quote": _clean(raw_json)[:1000],
        "evidence_locator": "json-ld.%s" % schema_type,
    }
    return category, candidate


def _page_evidence(
    body: bytes,
    source_url: str,
    retrieved_at: str,
    category: str,
) -> Tuple[List[Mapping[str, Any]], List[Mapping[str, Any]], Optional[Mapping[str, Any]]]:
    """Extract dated schema facts, otherwise a clearly labelled observation."""

    parser = _PageParser()
    parser.feed(body.decode("utf-8", "replace"))
    digest = _sha256(body)
    jobs: List[Mapping[str, Any]] = []
    news: List[Mapping[str, Any]] = []
    for item, raw_json in _jsonld_objects(parser.json_ld):
        result = _dated_schema_candidate(item, raw_json, source_url, retrieved_at, digest)
        if result is None:
            continue
        kind, candidate = result
        (jobs if kind == "jobs" else news).append(candidate)
    relevant = jobs if category == "jobs" else news
    if relevant:
        return jobs, news, None
    visible_text = _clean(" ".join(parser.text))
    if not visible_text:
        return jobs, news, None
    # This is an observation about a fetched page, not a job or news fact.  The
    # quote is a literal span from that page and carries its own bytes hash.
    observation = {
        "type": "page_observation",
        "category": category,
        "title": _clean(" ".join(parser.title)) or None,
        "observed_date": (_DATE_RE.search(visible_text).group(0) if _DATE_RE.search(visible_text) else None),
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "content_sha256": digest,
        "evidence_quote": visible_text[:1000],
        "evidence_locator": "html.visible-text",
    }
    return jobs, news, observation


def _decode_sitemap(body: bytes, url: str, max_bytes: int) -> bytes:
    if len(body) > max_bytes:
        raise ValueError("sitemap exceeded byte limit")
    if url.casefold().endswith(".gz") or body.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
            expanded = compressed.read(max_bytes + 1)
        if len(expanded) > max_bytes:
            raise ValueError("expanded sitemap exceeded byte limit")
        return expanded
    return body


def _parse_sitemap(body: bytes, url: str, max_bytes: int) -> Tuple[str, List[Tuple[str, Optional[str]]]]:
    xml = _decode_sitemap(body, url, max_bytes)
    lowered = xml[:4096].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("sitemap DTD/entity declarations are not allowed")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError("invalid sitemap XML") from exc
    root_name = root.tag.rsplit("}", 1)[-1].casefold()
    if root_name not in ("urlset", "sitemapindex"):
        raise ValueError("unsupported sitemap root")
    entries: List[Tuple[str, Optional[str]]] = []
    child_name = "url" if root_name == "urlset" else "sitemap"
    for child in root:
        if child.tag.rsplit("}", 1)[-1].casefold() != child_name:
            continue
        loc: Optional[str] = None
        lastmod: Optional[str] = None
        for value in child:
            name = value.tag.rsplit("}", 1)[-1].casefold()
            if name == "loc":
                loc = _clean(value.text)
            elif name == "lastmod":
                lastmod = _clean(value.text) or None
        if loc:
            entries.append((loc, lastmod))
    return root_name, entries


def _robots_allowed(text: str, url: str) -> bool:
    """Apply the longest-match robots rule, with Allow winning ties."""

    groups: List[Tuple[List[str], List[Tuple[bool, str]]]] = []
    agents: List[str] = []
    rules: List[Tuple[bool, str]] = []
    for raw_line in text.splitlines() + [""]:
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            if agents:
                groups.append((agents, rules))
            agents, rules = [], []
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key, value = key.strip().casefold(), value.strip()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.casefold())
        elif key in ("allow", "disallow") and agents:
            if value:
                rules.append((key == "allow", value))
    selected: List[Tuple[bool, str]] = []
    exact = [rules for group_agents, rules in groups if "signalpost" in group_agents]
    if exact:
        for rules in exact:
            selected.extend(rules)
    else:
        for group_agents, rules in groups:
            if "*" in group_agents:
                selected.extend(rules)
    if not selected:
        return True
    parsed = urllib.parse.urlsplit(url)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    matching = [(len(path), allow) for allow, path in selected if target.startswith(path)]
    if not matching:
        return True
    longest = max(length for length, _ in matching)
    return any(allow for length, allow in matching if length == longest)


class WebsiteFetcher:
    """Small urllib fetcher; no browser, JavaScript, or external parser."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_requests: int = 8,
        opener: Optional[Any] = None,
        max_sitemap_bytes: int = 262_144,
        max_sitemap_depth: int = 2,
        max_sitemaps: int = 4,
        max_pages: int = 6,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_requests = max_requests
        self._opener = opener or urllib.request.urlopen
        self.max_sitemap_bytes = max_sitemap_bytes
        self.max_sitemap_depth = max_sitemap_depth
        self.max_sitemaps = max_sitemaps
        self.max_pages = max_pages
        self._remaining: Optional[int] = None
        self.last_request_count = 0

    def fetch_url(self, url: str) -> FetchResponse:
        normal = _normalise_url(url)
        if not normal:
            raise ValueError("only absolute HTTP(S) URLs are allowed")
        if self._remaining is not None:
            if self._remaining <= 0:
                return FetchResponse(b"", 429, utc_now(), normal)
            self._remaining -= 1
        self.last_request_count += 1
        retrieved_at = utc_now()
        request = urllib.request.Request(normal, headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "Signalpost/0.1"})
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                body = response.read(1_048_577)
                if len(body) > 1_048_576:
                    return FetchResponse(body[:1_048_576], 413, retrieved_at, str(getattr(response, "url", normal)))
                return FetchResponse(body, int(getattr(response, "status", 200)), retrieved_at, str(getattr(response, "url", normal)))
        except urllib.error.HTTPError as exc:
            return FetchResponse(b"", int(exc.code), retrieved_at, normal)
        except (OSError, ValueError):
            return FetchResponse(b"", 0, retrieved_at, normal)

    def _robots_policy(
        self,
        url: str,
        policies: Dict[str, Tuple[urllib.robotparser.RobotFileParser, List[str], Mapping[str, Any]]],
    ) -> Optional[Tuple[urllib.robotparser.RobotFileParser, List[str], Mapping[str, Any]]]:
        """Fetch and cache robots.txt for each origin encountered."""

        normal = _normalise_url(url)
        if not normal:
            return None
        key = _origin(normal)
        if key in policies:
            return policies[key]
        robots_url = urllib.parse.urljoin(normal, "/robots.txt")
        response = self.fetch_url(robots_url)
        final = _normalise_url(response.final_url or robots_url)
        if not final or not same_registered_domain(final, normal):
            return None
        text = response.body.decode("utf-8", "replace")
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(text.splitlines() if response.status_code == 200 else [])
        sitemap_urls = [value for value in (parser.site_maps() or []) if _normalise_url(value)]
        metadata = {
            "source_url": final,
            "retrieved_at": response.retrieved_at or utc_now(),
            "content_sha256": _sha256(response.body),
            "status_code": response.status_code,
            "robots_text": text if response.status_code == 200 else "",
        }
        policy = (parser, sorted(set(sitemap_urls)), metadata)
        policies[key] = policy
        return policy

    def _fetch_sitemaps(
        self,
        website: str,
        policies: Dict[str, Tuple[urllib.robotparser.RobotFileParser, List[str], Mapping[str, Any]]],
    ) -> Tuple[List[Mapping[str, Any]], List[Tuple[str, str, Optional[str]]], Optional[Mapping[str, Any]]]:
        """Read bounded robots-declared/default sitemaps after identity proof."""

        initial = self._robots_policy(website, policies)
        if initial is None:
            return [], [], None
        _, declared, _ = initial
        default = urllib.parse.urljoin(website, "/sitemap.xml")
        queue: List[Tuple[str, int]] = [(url, 0) for url in declared]
        queue.append((default, 0))
        seen: set[str] = set()
        sitemap_records: List[Mapping[str, Any]] = []
        discovered: List[Tuple[str, str, Optional[str]]] = []
        while queue and len(seen) < self.max_sitemaps:
            candidate, depth = queue.pop(0)
            normal = _normalise_url(candidate)
            if not normal or normal in seen or not same_registered_domain(normal, website):
                continue
            seen.add(normal)
            policy = self._robots_policy(normal, policies)
            if policy is None or not _robots_allowed(str(policy[2].get("robots_text", "")), normal):
                continue
            response = self.fetch_url(normal)
            final = _normalise_url(response.final_url or normal)
            digest = _sha256(response.body)
            record: Dict[str, Any] = {
                "source_url": final or normal,
                "requested_url": normal,
                "retrieved_at": response.retrieved_at or utc_now(),
                "content_sha256": digest,
                "status_code": response.status_code,
                "depth": depth,
                "url_count": 0,
            }
            if not final or not same_registered_domain(final, website):
                record["error"] = "sitemap redirect left verified registered domain"
                sitemap_records.append(record)
                continue
            if response.status_code != 200:
                record["error"] = "sitemap returned HTTP %s" % response.status_code
                sitemap_records.append(record)
                continue
            try:
                kind, entries = _parse_sitemap(response.body, final, self.max_sitemap_bytes)
            except ValueError as exc:
                record["error"] = str(exc)
                sitemap_records.append(record)
                continue
            record["kind"] = kind
            record["url_count"] = len(entries)
            sitemap_records.append(record)
            for value, lastmod in entries[: max(0, self.max_pages * 20)]:
                linked = _normalise_url(urllib.parse.urljoin(final, value))
                if not linked or not same_registered_domain(linked, website):
                    continue
                if kind == "sitemapindex":
                    if depth < self.max_sitemap_depth:
                        queue.append((linked, depth + 1))
                    continue
                category = _classify_discovery_url(linked)
                if category:
                    discovered.append((linked, category, lastmod))
        unique: List[Tuple[str, str, Optional[str]]] = []
        used: set[str] = set()
        for item in discovered:
            if item[0] not in used:
                used.add(item[0])
                unique.append(item)
        return sitemap_records, unique[: self.max_pages], initial[2]

    def _fetch_discovered_pages(
        self,
        candidates: Sequence[Tuple[str, str, Optional[str]]],
        policies: Dict[str, Tuple[urllib.robotparser.RobotFileParser, List[str], Mapping[str, Any]]],
    ) -> Tuple[List[Mapping[str, Any]], List[Mapping[str, Any]], List[Mapping[str, Any]], List[Mapping[str, Any]]]:
        jobs: List[Mapping[str, Any]] = []
        news: List[Mapping[str, Any]] = []
        job_observations: List[Mapping[str, Any]] = []
        news_observations: List[Mapping[str, Any]] = []
        for url, category, _ in candidates[: self.max_pages]:
            policy = self._robots_policy(url, policies)
            if policy is None or not _robots_allowed(str(policy[2].get("robots_text", "")), url):
                continue
            response = self.fetch_url(url)
            final = _normalise_url(response.final_url or url)
            if not final or not same_registered_domain(final, url) or response.status_code != 200:
                continue
            page_jobs, page_news, observation = _page_evidence(
                response.body, final, response.retrieved_at or utc_now(), category
            )
            jobs.extend(page_jobs)
            news.extend(page_news)
            if observation is not None:
                (job_observations if category == "jobs" else news_observations).append(observation)
        return jobs, news, job_observations, news_observations

    def fetch(self, organisation_number: str, identity: Mapping[str, Any]) -> Mapping[str, ModuleResult]:
        """Compatibility adapter for Signalpost's existing official-data pipeline."""

        self.last_request_count = 0
        website = _registry_url(str(identity.get("website") or ""))
        if not website:
            return {}
        self._remaining = self.max_requests
        robots_url = urllib.parse.urljoin(website, "/robots.txt")
        policies: Dict[str, Tuple[urllib.robotparser.RobotFileParser, List[str], Mapping[str, Any]]] = {}
        initial_policy = self._robots_policy(website, policies)
        robots_metadata = initial_policy[2] if initial_policy else {
            "source_url": robots_url, "retrieved_at": utc_now(), "content_sha256": _sha256(b""), "status_code": 403
        }
        robots_digest = str(robots_metadata["content_sha256"])
        robots_status = int(robots_metadata["status_code"])
        if initial_policy is None:
            self._remaining = None
            return {
                "website_robots": ModuleResult("website_robots", str(robots_metadata["source_url"]), str(robots_metadata["retrieved_at"]), 403, None, "robots.txt redirect left registry-listed domain", robots_digest, source_class="company_owned"),
                "website_profile": ModuleResult("website_profile", website, str(robots_metadata["retrieved_at"]), 403, None, "robots.txt redirect left registry-listed domain", robots_digest, source_class="company_owned"),
            }
        robots_allowed = _robots_allowed(str(initial_policy[2].get("robots_text", "")), website)
        results: Dict[str, ModuleResult] = {
            "website_robots": ModuleResult(
                "website_robots", str(robots_metadata["source_url"]), str(robots_metadata["retrieved_at"]), robots_status,
                {"allowed": robots_allowed, "checked": robots_status == 200, "sitemaps": list(initial_policy[1])},
                "robots.txt disallows Signalpost" if not robots_allowed else None, robots_digest, source_class="company_owned",
            )
        }
        if not robots_allowed:
            results["website_profile"] = ModuleResult("website_profile", website, str(robots_metadata["retrieved_at"]), 403, None, "robots.txt disallows Signalpost", robots_digest, source_class="company_owned")
            self._remaining = None
            return results
        response = self.fetch_url(website)
        digest = _sha256(response.body)
        final_url = _normalise_url(response.final_url or website)
        if not final_url or not same_registered_domain(final_url, website):
            results["website_profile"] = ModuleResult("website_profile", website, response.retrieved_at or utc_now(), 403, None, "redirect left registry-listed domain", digest, source_class="company_owned")
            self._remaining = None
            return results
        parsed = parse_static_html(
            response.body,
            final_url,
            organisation_number,
            str(identity.get("name") or ""),
            response.retrieved_at,
            identity.get("business_address") or identity.get("forretningsadresse"),
            True,
        )
        body = parsed.to_dict()
        error = None if response.status_code == 200 and parsed.identity_proven else "website did not corroborate exact registry identity"
        result = ModuleResult("website_profile", parsed.source_url, parsed.retrieved_at, response.status_code, body, error, digest, source_class="company_owned")
        results.update({
            "website_profile": result,
        })
        # No sitemap or child page is consulted until the homepage proves the
        # registry identity.  URL classification below is discovery only.
        if response.status_code != 200 or not parsed.identity_proven:
            results.update({
                "hiring_activity": ModuleResult("hiring_activity", parsed.source_url, parsed.retrieved_at, response.status_code, {"jobs": [], "careers": [], "page_observations": []}, error, digest, source_class="company_owned"),
                "public_activity": ModuleResult("public_activity", parsed.source_url, parsed.retrieved_at, response.status_code, {"news": [], "dated_text": [], "page_observations": []}, error, digest, source_class="company_owned"),
            })
            self._remaining = None
            return results

        # A redirect may land on another host in the same registered domain;
        # obtain that host's robots policy before doing any subsequent fetch.
        final_policy = self._robots_policy(final_url, policies)
        if final_policy is None or not _robots_allowed(str(final_policy[2].get("robots_text", "")), final_url):
            reason = "robots.txt disallows redirected homepage" if final_policy else "redirected homepage robots.txt could not be verified"
            results["website_sitemap"] = ModuleResult("website_sitemap", final_url, parsed.retrieved_at, 403, {"sitemaps": [], "candidate_pages": []}, reason, digest, source_class="company_owned")
            results["hiring_activity"] = ModuleResult("hiring_activity", parsed.source_url, parsed.retrieved_at, 403, {"jobs": [], "careers": [], "page_observations": []}, reason, digest, source_class="company_owned")
            results["public_activity"] = ModuleResult("public_activity", parsed.source_url, parsed.retrieved_at, 403, {"news": [], "dated_text": [], "page_observations": []}, reason, digest, source_class="company_owned")
            self._remaining = None
            return results

        sitemap_records, sitemap_candidates, _ = self._fetch_sitemaps(final_url, policies)
        direct_candidates: List[Tuple[str, str, Optional[str]]] = []
        for category in ("jobs", "news"):
            direct_candidates.extend((url, category, None) for url in parsed.links.get(category, ()))
        all_candidates: List[Tuple[str, str, Optional[str]]] = []
        seen_candidates: set[str] = set()
        for candidate in direct_candidates + sitemap_candidates:
            if candidate[0] not in seen_candidates:
                seen_candidates.add(candidate[0])
                all_candidates.append(candidate)
        jobs, news, job_observations, news_observations = self._fetch_discovered_pages(all_candidates, policies)
        sitemap_source = sitemap_records[0] if sitemap_records else None
        sitemap_body = {
            "sitemaps": sitemap_records,
            "candidate_pages": [
                {"source_url": url, "category": category, "sitemap_lastmod": lastmod, "discovery_only": True}
                for url, category, lastmod in sitemap_candidates
            ],
        }
        results["website_sitemap"] = ModuleResult(
            "website_sitemap",
            str(sitemap_source["source_url"] if sitemap_source else urllib.parse.urljoin(final_url, "/sitemap.xml")),
            str(sitemap_source["retrieved_at"] if sitemap_source else parsed.retrieved_at),
            int(sitemap_source["status_code"] if sitemap_source else 404),
            sitemap_body,
            None,
            str(sitemap_source["content_sha256"] if sitemap_source else digest),
            source_class="company_owned",
        )
        results["hiring_activity"] = ModuleResult(
            "hiring_activity", parsed.source_url, parsed.retrieved_at, response.status_code,
            {"jobs": jobs, "careers": job_observations, "page_observations": job_observations}, None, digest, source_class="company_owned"
        )
        results["public_activity"] = ModuleResult(
            "public_activity", parsed.source_url, parsed.retrieved_at, response.status_code,
            {"news": news, "dated_text": sorted({str(item["date"]) for item in news}), "page_observations": news_observations}, None, digest, source_class="company_owned"
        )
        self._remaining = None
        return results


def parse_company_html(html: str, page_url: str, organisation_number: str, legal_name: Optional[str]) -> Dict[str, Any]:
    """Backward-compatible dictionary view of :func:`parse_static_html`."""

    return parse_static_html(html, page_url, organisation_number, legal_name).to_dict()


class WebsiteEnabledAdapter:
    """Decorate an official adapter without coupling registry and web transport."""

    def __init__(self, base: Any, fetcher: WebsiteFetcher):
        self.base = base
        self.fetcher = fetcher
        self.revision = getattr(base, "revision", "base") + ":website-v2"
        self.reference_time = getattr(base, "reference_time", utc_now())
        self.deterministic = getattr(base, "deterministic", False)
        self.last_request_count = 0

    def fetch_company(self, organisation_number: str) -> Mapping[str, ModuleResult]:
        results = dict(self.base.fetch_company(organisation_number))
        identity = results.get("legal_identity")
        if identity is not None and identity.available and isinstance(identity.body, dict):
            results.update(
                self.fetcher.fetch(
                    organisation_number,
                    {
                        "website": identity.body.get("hjemmeside"),
                        "name": identity.body.get("navn"),
                        "business_address": identity.body.get("forretningsadresse"),
                    },
                )
            )
        self.last_request_count = int(getattr(self.base, "last_request_count", 0)) + int(getattr(self.fetcher, "last_request_count", 0))
        return results


__all__ = [
    "CandidateClaim",
    "FetchResponse",
    "WebsiteEnrichment",
    "WebsiteEnabledAdapter",
    "WebsiteEnricher",
    "WebsiteFetcher",
    "is_allowed_url",
    "parse_company_html",
    "parse_static_html",
    "registered_domain",
    "same_registered_domain",
]
