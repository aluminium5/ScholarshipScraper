"""Vidyasaarathi scraper (spec §7.3).

Verified against the live portal on 17 Oct 2026.

The page is server-rendered Java/Spring, but the scheme cards are *not* in the
HTML: the open schemes are embedded in the page as a JavaScript array literal,

    var a=[{"smScholarshipName": ..., "smSchemeEndDate": "30/10/2026", ...}, ...];

which the page's own getOpenSchemes()/getSchemeList() functions render into
cards. Closed schemes come separately from an AJAX call to getClosedSchemes,
which this scraper ignores.

Two traps worth recording, both of which produced wrong results first time:

1. The string "Currently No Schemes are Available" is always present, because it
   is the else-branch inside the renderer's JavaScript source. Testing for it in
   the raw page text reports "no schemes" even when 15 are open. The empty check
   therefore runs against the page with <script> and <style> stripped out.
2. The page is served as ISO-8859-1 and contains cp1252 bytes (0x92 smart
   quotes), so decoding it as UTF-8 raises. The response encoding is pinned to
   cp1252, which is a superset of latin-1 for these bytes.

Deep links
----------
Each record carries smSchemeStaticHtmlFileName ("1765_12.html") and the page
builds a detail URL as resources/<smEntityCode>/<smSchemeId>_<version>.html.
Every such URL 404s without a session, so there is no usable per-scheme public
page. As with NSP (spec §6), apply_url is therefore the scheme *listing* page --
a real path, never the bare homepage -- and the UI shows a note telling the
student which scheme to select after logging in. `otr_note`-style guidance is
carried in the description.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

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

BASE_URL = "https://www.vidyasaarathi.co.in"
LIST_URL = f"{BASE_URL}/Vidyasaarathi/scholarship"

#: Where Apply sends the student: the Open Schemes listing, not the homepage.
APPLY_URL = LIST_URL

_EMPTY_MARKERS = (
    "currently no schemes are available",
    "no schemes are available",
    "no scheme available",
    "no records found",
)

#: The server-embedded open-schemes array.
_OPEN_ARRAY = re.compile(r"var\s+a\s*=\s*(\[.*?\])\s*;\s*[\r\n]", re.S)

_GENDER_TAGS = {"F": "girls", "M": None, "A": None}


def _visible_text(html: str) -> str:
    """Page text with scripts and styles removed.

    The empty-state message lives in JavaScript, so it must not be read from
    the raw source (see the module docstring).
    """
    soup = BeautifulSoup(html, "lxml")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return normalize_space(soup.get_text(" ", strip=True)).lower()


def _amount(raw: object) -> str | None:
    """Format a rupee amount from the portal's numeric strings."""
    if raw in (None, "", "null"):
        return None
    try:
        value = float(str(raw))
    except (TypeError, ValueError):
        return normalize_space(str(raw))[:300] or None
    if value <= 0:
        return None
    # Indian grouping reads better than a bare float here.
    return f"INR {int(round(value)):,}"


def _clean_blurb(raw: object, limit: int = 900) -> str | None:
    if raw in (None, "", "null"):
        return None
    value = str(raw)
    # Only hand it to the HTML parser when it actually looks like markup;
    # a short plain string makes BeautifulSoup warn about filenames.
    if "<" in value and ">" in value:
        value = BeautifulSoup(value, "lxml").get_text(" ", strip=True)
    text = normalize_space(value)
    if not text:
        return None
    return text[: limit - 1] + "…" if len(text) > limit else text


def _map_record(raw: dict, today: date) -> ScrapedScholarship | None:
    if not isinstance(raw, dict):
        return None

    title = _clean_blurb(raw.get("smScholarshipName"), limit=400)
    if not title or len(title) < 6:
        return None

    deadline = parse_date(raw.get("smSchemeEndDate"))
    if deadline is not None and deadline < today:
        return None

    provider = _clean_blurb(raw.get("smEntityName"), limit=200)
    description = _clean_blurb(
        raw.get("smSchemeDesc") or raw.get("smScholarshipDesc"), limit=700
    )

    eligibility_bits: list[str] = []
    if raw.get("smSchemeStateCriteriaValue"):
        eligibility_bits.append(f"State: {raw['smSchemeStateCriteriaValue']}")
    if raw.get("smSchemeMinPercentageCriteria"):
        eligibility_bits.append(
            f"Minimum marks: {raw['smSchemeMinPercentageCriteria']}%"
        )
    income = _amount(raw.get("smFamilyIncomeMax"))
    if income:
        eligibility_bits.append(f"Family income up to {income}")
    certificates = _clean_blurb(raw.get("smRequiredCertificatesInstruction"), limit=500)
    if certificates:
        eligibility_bits.append(certificates)
    eligibility = " | ".join(eligibility_bits) or None

    scheme_id = str(raw.get("smSchemeId") or "").strip()
    external_id = scheme_id or stable_id("vidyasaarathi", title)

    tags = infer_tags(title, " ".join(filter(None, [description, eligibility])))
    gender_tag = _GENDER_TAGS.get(str(raw.get("smSchemeGenderCriteria") or "").upper())
    if gender_tag and gender_tag not in tags:
        tags.append(gender_tag)
    if income and "need" not in tags:
        tags.append("need")

    # The portal has no public per-scheme page, so tell the student exactly
    # which scheme to pick after logging in (same pattern as NSP's OTR note).
    note = (
        "Vidyasaarathi requires a login. Open the Open Schemes tab and select: "
        f"{title}"
    )
    return ScrapedScholarship(
        source="vidyasaarathi",
        external_id=external_id,
        title=title,
        provider=provider,
        apply_url=APPLY_URL,
        info_url=APPLY_URL,
        deadline=deadline,
        opens_at=parse_date(raw.get("smSchemeStartDate")),
        award_amount=_amount(raw.get("smScholarshipAmount")),
        eligibility=eligibility,
        description=" ".join(filter(None, [description, note])),
        level=guess_level(f"{title} {description or ''}"),
        tags=tags,
    )


def parse_open_schemes(html: str, today: date | None = None) -> list[ScrapedScholarship]:
    """Parse the embedded open-schemes array. Returns [] when none are open."""
    today = today or date.today()

    match = _OPEN_ARRAY.search(html)
    if match is None:
        # No array at all: only then is the rendered empty-state meaningful.
        if any(marker in _visible_text(html) for marker in _EMPTY_MARKERS):
            log.info("vidyasaarathi: portal reports no open schemes")
        else:
            log.warning(
                "vidyasaarathi: could not find the embedded open-schemes array; "
                "the page layout may have changed"
            )
        return []

    try:
        records = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        log.warning("vidyasaarathi: embedded scheme array is not valid JSON: %s", exc)
        return []

    if not isinstance(records, list):
        return []

    results: list[ScrapedScholarship] = []
    seen: set[str] = set()
    for raw in records:
        mapped = _map_record(raw, today)
        if mapped is None or mapped.external_id in seen:
            continue
        seen.add(mapped.external_id)
        results.append(mapped)

    log.info(
        "vidyasaarathi: %s open schemes (%s embedded records)", len(results), len(records)
    )
    return results


#: Kept for the previous name used by tests and callers.
parse_vidyasaarathi_html = parse_open_schemes


class VidyasaarathiScraper(BaseScraper):
    source = "vidyasaarathi"
    verified = True

    def fetch(self, client: httpx.Client) -> list[ScrapedScholarship]:
        response = get_with_retries(client, LIST_URL)
        # Served as ISO-8859-1 with cp1252 bytes; decoding as UTF-8 raises.
        response.encoding = "cp1252"
        return parse_open_schemes(response.text)
