"""Buddy4Study scraper (spec §7.2).

STATUS: the parser is implemented and unit-tested, but no live listing payload
has been captured yet. See "Wiring up the live endpoint" below.

Buddy4Study is a Next.js app. As of 17 Oct 2026 the /scholarships listing is
rendered entirely on the client:

  * the served HTML is a ~22 KB shell with no scholarship markup;
  * <script id="__NEXT_DATA__"> carries only i18n strings, no scholarship list;
  * the data is fetched at runtime from https://api.buddy4study.com/api/v1.0/
    (that base URL is hard-coded in the page bundle), but the listing path is in
    a lazily-loaded chunk and is not discoverable without DevTools;
  * robots.txt allows /scholarships and /page/*, and disallows only /media-url/*
    and /UID/*, so scraping these pages is permitted.

Wiring up the live endpoint
---------------------------
1. Open https://www.buddy4study.com/scholarships in a browser.
2. DevTools -> Network -> Fetch/XHR, then reload and scroll the list.
3. Find the request returning JSON scholarship objects. Copy its full URL.
4. Put it in LISTING_ENDPOINT below (and adjust RESULT_KEYS if the array is
   nested under a different key).

Nothing else needs to change: _map_record already tolerates the common field
spellings, and every record without a resolvable slug is skipped so the apply
link can never degrade to the portal homepage (spec §6).

Until then fetch() returns [] and logs a warning, which leaves Buddy4Study rows
in the database untouched (spec §7.5.3) and keeps the daily refresh green.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from backend.scrapers.base import (
    BaseScraper,
    ScrapedScholarship,
    get_with_retries,
    guess_level,
    infer_tags,
    normalize_space,
    parse_date,
    stable_id,
)

log = logging.getLogger(__name__)

LISTING_URL = "https://www.buddy4study.com/scholarships"
PAGE_PREFIX = "https://www.buddy4study.com/page/"

#: Paste the JSON listing URL found via DevTools here (see module docstring).
LISTING_ENDPOINT: str | None = None

#: Keys under which a payload might hold the scholarship array.
RESULT_KEYS = ("content", "scholarships", "results", "data", "items", "list", "docs")

_TITLE_KEYS = ("name", "title", "scholarshipName", "schemeName")
_SLUG_KEYS = ("slug", "pageSlug", "seoSlug", "url", "scholarshipSlug", "pageUrl")
_DEADLINE_KEYS = (
    "applicationDeadline", "deadline", "lastDate", "endDate",
    "applicationEndDate", "closingDate", "expiryDate",
)
_OPENS_KEYS = ("startDate", "applicationStartDate", "openDate", "launchDate")
_AWARD_KEYS = ("awardAmount", "award", "amount", "benefits", "prize", "scholarshipAmount")
_ELIGIBILITY_KEYS = ("eligibility", "eligibilityCriteria", "whoCanApply", "criteria")
_DESC_KEYS = ("description", "shortDescription", "about", "summary", "aboutProgram")
_PROVIDER_KEYS = ("provider", "donor", "company", "organisation", "organization", "sponsor")


def _first_str(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """First non-empty string among `keys`, flattening the odd nested object."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in ("name", "title", "value", "text"):
                inner = value.get(nested)
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
        if isinstance(value, (int, float)) and key in _DEADLINE_KEYS + _OPENS_KEYS:
            return str(value)
    return None


def _html_to_text(value: str | None, limit: int = 1200) -> str | None:
    """Several of these fields arrive as HTML fragments."""
    if not value:
        return None
    text = normalize_space(BeautifulSoup(value, "lxml").get_text(" ", strip=True))
    if not text:
        return None
    return text[: limit - 1] + "…" if len(text) > limit else text


def _slug_from(record: dict[str, Any]) -> str | None:
    """Extract the page slug. Returns None if there is no usable slug."""
    raw = _first_str(record, _SLUG_KEYS)
    if not raw:
        return None
    # Accept a bare slug or any absolute/relative URL containing /page/<slug>.
    match = re.search(r"/page/([A-Za-z0-9._~-]+)", raw)
    slug = match.group(1) if match else raw.strip().strip("/")
    if "/" in slug or not re.fullmatch(r"[A-Za-z0-9._~-]{3,200}", slug):
        return None
    return slug


def _map_record(record: dict[str, Any]) -> ScrapedScholarship | None:
    """Map one API record. Returns None when the record cannot be deep-linked."""
    if not isinstance(record, dict):
        return None

    title = _first_str(record, _TITLE_KEYS)
    slug = _slug_from(record)
    if not title or not slug:
        # No scholarship-specific URL means we skip rather than link the
        # portal homepage (spec §6).
        log.info("buddy4study: skipping record without title/slug: %r", title or record)
        return None

    eligibility = _html_to_text(_first_str(record, _ELIGIBILITY_KEYS))
    description = _html_to_text(_first_str(record, _DESC_KEYS), limit=600)
    award = _first_str(record, _AWARD_KEYS)

    external_id = (
        str(record.get("id") or record.get("scholarshipId") or "").strip()
        or stable_id("buddy4study", slug)
    )

    blurb = " ".join(filter(None, [title, eligibility or "", description or ""]))
    return ScrapedScholarship(
        source="buddy4study",
        external_id=external_id,
        title=title,
        provider=_first_str(record, _PROVIDER_KEYS),
        apply_url=f"{PAGE_PREFIX}{slug}",
        info_url=f"{PAGE_PREFIX}{slug}",
        deadline=parse_date(_first_str(record, _DEADLINE_KEYS)),
        opens_at=parse_date(_first_str(record, _OPENS_KEYS)),
        award_amount=normalize_space(award)[:300] if award else None,
        eligibility=eligibility,
        description=description,
        level=guess_level(blurb),
        tags=infer_tags(blurb),
    )


def find_records(payload: Any, _depth: int = 0) -> list[dict[str, Any]]:
    """Locate the scholarship array inside an arbitrarily wrapped payload.

    Kept separate from mapping so a changed envelope only needs this fixed.
    """
    if _depth > 6:
        return []
    if isinstance(payload, list):
        dicts = [p for p in payload if isinstance(p, dict)]
        # A scholarship list is recognisable by its title + slug fields.
        if dicts and any(
            _first_str(d, _TITLE_KEYS) and _slug_from(d) for d in dicts[:10]
        ):
            return dicts
        return []
    if isinstance(payload, dict):
        for key in RESULT_KEYS:
            if key in payload:
                found = find_records(payload[key], _depth + 1)
                if found:
                    return found
        for value in payload.values():
            if isinstance(value, (dict, list)):
                found = find_records(value, _depth + 1)
                if found:
                    return found
    return []


def parse_next_data(html: str) -> list[ScrapedScholarship]:
    """Parse the listing out of __NEXT_DATA__, if the site ever inlines it."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag is None or not tag.string:
        log.warning("buddy4study: no __NEXT_DATA__ script in the listing HTML")
        return []
    try:
        payload = json.loads(tag.string)
    except json.JSONDecodeError as exc:
        log.warning("buddy4study: __NEXT_DATA__ is not valid JSON: %s", exc)
        return []
    return parse_payload(payload)


def parse_payload(payload: Any) -> list[ScrapedScholarship]:
    """Map a JSON payload (from __NEXT_DATA__ or the API) to scholarships."""
    records = find_records(payload)
    if not records:
        log.warning("buddy4study: no scholarship array found in payload")
        return []

    results: list[ScrapedScholarship] = []
    seen: set[str] = set()
    for record in records:
        mapped = _map_record(record)
        if mapped is None or mapped.external_id in seen:
            continue
        seen.add(mapped.external_id)
        results.append(mapped)
    return results


class Buddy4StudyScraper(BaseScraper):
    source = "buddy4study"
    # Flipped to True once LISTING_ENDPOINT is set and confirmed against a fixture.
    verified = False

    def fetch(self, client: httpx.Client) -> list[ScrapedScholarship]:
        if LISTING_ENDPOINT:
            response = get_with_retries(client, LISTING_ENDPOINT)
            try:
                payload = response.json()
            except ValueError:
                log.warning("buddy4study: LISTING_ENDPOINT did not return JSON")
                return []
            records = parse_payload(payload)
            log.info("buddy4study: parsed %s scholarships from API", len(records))
            return records

        # Fall back to the inlined payload; currently empty, hence the warning.
        response = get_with_retries(client, LISTING_URL)
        response.encoding = "utf-8"
        records = parse_next_data(response.text)
        if not records:
            log.warning(
                "buddy4study: listing is client-rendered and LISTING_ENDPOINT is "
                "unset, so 0 scholarships were found. See this module's docstring "
                "for how to capture the JSON endpoint. Returning [] leaves "
                "existing buddy4study rows untouched."
            )
        return records
