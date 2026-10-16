"""Buddy4Study scraper (spec §7.2).

The /scholarships listing is rendered entirely on the client, so the approach the
spec suggests as a first try (parsing __NEXT_DATA__ on the listing page) yields
nothing: that payload holds only i18n strings. The runtime JSON API
(https://api.buddy4study.com/api/v1.0/) needs an endpoint path that is not
discoverable without DevTools.

What works instead, verified on 17 Oct 2026, is the site's own per-scholarship
pages:

  * robots.txt allows /scholarship/* and /page/*, and sitemap1.xml (declared in
    robots.txt) lists ~1350 /scholarship/<slug> URLs, each with <lastmod>;
  * every such page server-renders a full <script id="__NEXT_DATA__"> payload
    containing props.pageProps.scholarship.brandPage.scholarships[], an array of
    that programme's editions across years;
  * each edition carries title, slug, pageSlug, deadline (ISO), deadlineDateDiff,
    purposeAward, applicationLaunchDate and eligibility HTML;
  * pageSlug is "page/<brand-slug>", which is exactly the per-scholarship deep
    link the spec requires for this source (spec §6).

So discovery comes from the sitemap and the data from each page's embedded JSON.

Request budget
--------------
Crawling all 1350 pages would never fit in a serverless invocation, so the
crawl is capped by MAX_PAGES (override with BUDDY4STUDY_MAX_PAGES) and the
most-recently-modified pages are visited first, which is where new and reopened
scholarships show up. NSP already supplies the bulk of the catalogue; this
source adds private and corporate variety.

If the JSON listing endpoint is ever captured from DevTools, set
LISTING_ENDPOINT and it is used instead of the crawl.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import date
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

BASE = "https://www.buddy4study.com"
LISTING_URL = f"{BASE}/scholarships"
SITEMAP_URL = f"{BASE}/sitemap1.xml"
PAGE_PREFIX = f"{BASE}/page/"

#: Optional: a JSON listing endpoint captured from DevTools (see docstring).
LISTING_ENDPOINT: str | None = None

#: How many per-scholarship pages to crawl in one refresh. Each page costs one
#: request, so this is what keeps the daily refresh inside the serverless time
#: limit. Most pages describe a programme whose current edition has already
#: closed, so expect only a handful of open records per run; raise this when
#: running the ingest somewhere without a request timeout.
MAX_PAGES = int(os.getenv("BUDDY4STUDY_MAX_PAGES", "25"))

#: Politeness delay between page fetches, in seconds.
CRAWL_DELAY = float(os.getenv("BUDDY4STUDY_CRAWL_DELAY", "0.25"))

#: Title served for a slug that does not exist (the site soft-404s with HTTP 200).
GENERIC_TITLE = "Scholarship portal for Indian students"

RESULT_KEYS = ("scholarships", "content", "results", "data", "items", "list", "docs")

_TITLE_KEYS = ("title", "name", "scholarshipName", "schemeName")
_SLUG_KEYS = ("pageSlug", "slug", "seoSlug", "url", "scholarshipSlug", "pageUrl")
_DEADLINE_KEYS = (
    "deadline", "applicationDeadline", "lastDate", "endDate",
    "applicationEndDate", "closingDate", "expiryDate",
)
_OPENS_KEYS = (
    "applicationLaunchDate", "startDate", "applicationStartDate", "openDate",
)
_AWARD_KEYS = (
    "purposeAward", "awardAmount", "award", "amount", "benefits", "scholarshipAmount",
)
_ELIGIBILITY_KEYS = ("eligibility", "eligibilityCriteria", "whoCanApply", "criteria")
_DESC_KEYS = ("description", "shortDescription", "about", "summary", "aboutProgram")
_PROVIDER_KEYS = (
    "provider", "donor", "company", "organisation", "organization", "sponsor", "brandName",
)


# ----------------------------------------------------------------- field helpers
def _first_str(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in ("name", "title", "value", "text"):
                inner = value.get(nested)
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if key in _DEADLINE_KEYS + _OPENS_KEYS:
                return str(value)
    return None


def _html_to_text(value: str | None, limit: int = 1200) -> str | None:
    """Eligibility and description arrive as HTML fragments."""
    if not value:
        return None
    text = normalize_space(BeautifulSoup(value, "lxml").get_text(" ", strip=True))
    if not text or text.upper() == "NA":
        return None
    return text[: limit - 1] + "…" if len(text) > limit else text


def _brand_slug(record: dict[str, Any]) -> str | None:
    """The brand page slug, which is what Apply must open (spec §6)."""
    raw = _first_str(record, _SLUG_KEYS)
    if not raw:
        return None
    # "page/kotak-kanya-scholarship", "/page/x", a full URL, or a bare slug.
    match = re.search(r"(?:^|/)page/([A-Za-z0-9._~-]+)", raw)
    slug = match.group(1) if match else raw.strip().strip("/")
    if "/" in slug or not re.fullmatch(r"[A-Za-z0-9._~-]{3,200}", slug):
        return None
    return slug


def _map_record(record: dict[str, Any], today: date) -> ScrapedScholarship | None:
    """Map one edition. Returns None if it is closed or cannot be deep-linked."""
    if not isinstance(record, dict):
        return None

    title = _first_str(record, _TITLE_KEYS)
    slug = _brand_slug(record)
    if not title or not slug:
        return None

    deadline = parse_date(_first_str(record, _DEADLINE_KEYS))
    # Each brand page lists several years of editions; keep only ones still open.
    # An edition with no deadline at all is kept and sorts last in the UI.
    if deadline is not None and deadline < today:
        return None

    eligibility = _html_to_text(_first_str(record, _ELIGIBILITY_KEYS))
    description = _html_to_text(_first_str(record, _DESC_KEYS), limit=600)
    award = _first_str(record, _AWARD_KEYS)
    apply_url = f"{PAGE_PREFIX}{slug}"

    # The edition slug is year-specific and stable; fall back to a title hash.
    external_id = (
        str(record.get("slug") or "").strip()
        or str(record.get("id") or record.get("scholarshipId") or "").strip()
        or stable_id("buddy4study", title)
    )

    detail = " ".join(filter(None, [eligibility or "", description or ""]))
    return ScrapedScholarship(
        source="buddy4study",
        external_id=external_id,
        title=title,
        provider=_first_str(record, _PROVIDER_KEYS),
        apply_url=apply_url,
        info_url=apply_url,
        deadline=deadline,
        opens_at=parse_date(_first_str(record, _OPENS_KEYS)),
        award_amount=normalize_space(award)[:300] if award else None,
        eligibility=eligibility,
        description=description,
        # Title first so the programme's own wording decides the level.
        level=guess_level(f"{title} {detail}"),
        tags=infer_tags(title, detail),
    )


# --------------------------------------------------------------------- parsing
def find_records(payload: Any, _depth: int = 0) -> list[dict[str, Any]]:
    """Locate the scholarship array inside an arbitrarily wrapped payload."""
    if _depth > 8:
        return []
    if isinstance(payload, list):
        dicts = [p for p in payload if isinstance(p, dict)]
        if dicts and any(
            _first_str(d, _TITLE_KEYS) and _brand_slug(d) for d in dicts[:10]
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


def extract_next_data(html: str) -> Any | None:
    """Return the parsed __NEXT_DATA__ payload, or None."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag is None or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError as exc:
        log.warning("buddy4study: __NEXT_DATA__ is not valid JSON: %s", exc)
        return None


def is_soft_404(html: str) -> bool:
    """The site answers unknown slugs with HTTP 200 and its generic title."""
    match = re.search(r"<title>([^<]*)", html)
    return bool(match) and match.group(1).strip().startswith(GENERIC_TITLE)


def parse_payload(payload: Any, today: date | None = None) -> list[ScrapedScholarship]:
    """Map a JSON payload (page-embedded or API) to open scholarships."""
    today = today or date.today()
    records = find_records(payload)
    if not records:
        return []

    results: list[ScrapedScholarship] = []
    seen: set[str] = set()
    for record in records:
        mapped = _map_record(record, today)
        if mapped is None or mapped.external_id in seen:
            continue
        seen.add(mapped.external_id)
        results.append(mapped)
    return results


def parse_detail_page(html: str, today: date | None = None) -> list[ScrapedScholarship]:
    """Parse the open editions out of one /scholarship/<slug> or /page/<slug> page."""
    if is_soft_404(html):
        return []
    payload = extract_next_data(html)
    if payload is None:
        return []
    return parse_payload(payload, today)


def parse_sitemap(xml: str) -> list[str]:
    """Return /scholarship/<slug> URLs, most recently modified first."""
    entries: list[tuple[str, str]] = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
        if not loc:
            continue
        url = loc.group(1)
        if not re.match(rf"^{re.escape(BASE)}/scholarship/[^/]+/?$", url):
            continue
        lastmod = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", block)
        entries.append((lastmod.group(1) if lastmod else "", url))

    if not entries:
        # Some sitemaps omit <url> wrappers; fall back to bare <loc> scanning.
        for url in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
            if re.match(rf"^{re.escape(BASE)}/scholarship/[^/]+/?$", url):
                entries.append(("", url))

    # Newest lastmod first; ISO-8601 strings sort correctly as text.
    entries.sort(key=lambda e: e[0], reverse=True)

    ordered: list[str] = []
    seen: set[str] = set()
    for _, url in entries:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


# ---------------------------------------------------------------------- scraper
class Buddy4StudyScraper(BaseScraper):
    source = "buddy4study"
    verified = True

    def __init__(self, max_pages: int | None = None) -> None:
        self.max_pages = MAX_PAGES if max_pages is None else max_pages

    def fetch(self, client: httpx.Client) -> list[ScrapedScholarship]:
        if LISTING_ENDPOINT:
            response = get_with_retries(client, LISTING_ENDPOINT)
            try:
                payload = response.json()
            except ValueError:
                log.warning("buddy4study: LISTING_ENDPOINT did not return JSON")
                return []
            records = parse_payload(payload)
            log.info("buddy4study: %s scholarships from the API", len(records))
            return records

        sitemap = get_with_retries(client, SITEMAP_URL)
        sitemap.encoding = "utf-8"
        urls = parse_sitemap(sitemap.text)
        if not urls:
            log.warning("buddy4study: no /scholarship/ URLs in the sitemap")
            return []

        log.info(
            "buddy4study: %s scholarship pages in the sitemap, crawling the %s newest",
            len(urls),
            min(self.max_pages, len(urls)),
        )

        today = date.today()
        results: list[ScrapedScholarship] = []
        seen: set[str] = set()
        failures = 0

        for index, url in enumerate(urls[: self.max_pages]):
            if index:
                time.sleep(CRAWL_DELAY)
            try:
                page = get_with_retries(client, url, retries=1)
                page.encoding = "utf-8"
                for record in parse_detail_page(page.text, today):
                    if record.external_id in seen:
                        continue
                    seen.add(record.external_id)
                    results.append(record)
            except Exception as exc:  # noqa: BLE001 - one page must not stop the crawl
                failures += 1
                log.warning("buddy4study: %s failed: %s", url, exc)

        if failures and not results:
            # Every page failed: raise so ingest treats this as an error and
            # leaves existing buddy4study rows untouched (spec §7.5.3).
            raise RuntimeError(f"all {failures} buddy4study page fetches failed")

        log.info("buddy4study: parsed %s open scholarships", len(results))
        return results
