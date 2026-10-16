"""Shared scraper contract and parsing helpers (spec §7).

Every scraper returns a list of ScrapedScholarship. A scraper that cannot find a
scholarship-specific apply URL must skip the record rather than fall back to a
portal homepage (spec §6).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx

log = logging.getLogger(__name__)

# A real browser UA: several of these portals reject obvious bot agents.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

TIMEOUT_SECONDS = 15.0
MAX_RETRIES = 2

VALID_LEVELS = {"school", "ug", "pg", "phd", "any"}


@dataclass
class ScrapedScholarship:
    source: str
    external_id: str
    title: str
    apply_url: str
    provider: str | None = None
    deadline: date | None = None
    opens_at: date | None = None
    info_url: str | None = None
    award_amount: str | None = None
    eligibility: str | None = None
    description: str | None = None
    level: str = "any"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = normalize_space(self.title)
        if self.provider:
            self.provider = normalize_space(self.provider)
        if self.level not in VALID_LEVELS:
            self.level = "any"
        # Deduplicate tags while keeping a stable order for diff-friendly rows.
        seen: set[str] = set()
        ordered: list[str] = []
        for t in self.tags:
            t = t.strip().lower()
            if t and t not in seen:
                seen.add(t)
                ordered.append(t)
        self.tags = ordered


class BaseScraper:
    """Subclasses set `source` and implement `fetch`."""

    source: str = "base"
    #: False marks a scraper whose live markup has not been verified against a
    #: fixture; the registry still runs it, but the README flags it.
    verified: bool = True

    def fetch(self, client: httpx.Client) -> list[ScrapedScholarship]:
        raise NotImplementedError


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        },
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def get_with_retries(
    client: httpx.Client, url: str, *, retries: int = MAX_RETRIES
) -> httpx.Response:
    """GET with a bounded number of retries. Raises the last error on failure."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001 - re-raised below
            last = exc
            log.warning(
                "GET %s failed (attempt %s/%s): %s", url, attempt + 1, retries + 1, exc
            )
    assert last is not None
    raise last


def normalize_space(text: str) -> str:
    """Collapse all whitespace runs to single spaces.

    Essential for these portals: NSP renders labels like
    'Student Application  Open till' with doubled spaces and stray newlines.
    """
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


_DATE_PATTERNS = (
    # 31-10-2026, 31/10/2026, 31.10.2026
    (re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$"), "dmy"),
    # 2026-10-31
    (re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$"), "ymd"),
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_TEXTUAL_DATE = re.compile(
    r"^(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})$"
)
_TEXTUAL_DATE_MDY = re.compile(
    r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*(?:st|nd|rd|th)?,?\s+(\d{4})$"
)


def parse_date(raw: str | None) -> date | None:
    """Parse the date formats these portals use. Returns None if unparseable.

    Handles DD-MM-YYYY, YYYY-MM-DD, '31 October 2026' and 'October 31, 2026'.
    Day-first is assumed for ambiguous numeric dates, which is the Indian
    convention and what NSP emits.
    """
    if not raw:
        return None
    text = normalize_space(str(raw))
    if not text:
        return None

    for pattern, order in _DATE_PATTERNS:
        m = pattern.match(text)
        if not m:
            continue
        a, b, c = (int(g) for g in m.groups())
        day, month, year = (a, b, c) if order == "dmy" else (c, b, a)
        try:
            return date(year, month, day)
        except ValueError:
            return None

    for pattern, day_first in ((_TEXTUAL_DATE, True), (_TEXTUAL_DATE_MDY, False)):
        m = pattern.match(text)
        if not m:
            continue
        g1, g2, g3 = m.groups()
        day_s, month_s = (g1, g2) if day_first else (g2, g1)
        month = _MONTHS.get(month_s[:4].lower()) or _MONTHS.get(month_s[:3].lower())
        if not month:
            return None
        try:
            return date(int(g3), month, int(day_s))
        except ValueError:
            return None

    # Epoch milliseconds, as some JSON APIs return.
    if text.isdigit() and len(text) in (10, 13):
        value = int(text)
        try:
            return datetime.fromtimestamp(value / 1000 if len(text) == 13 else value).date()
        except (ValueError, OSError, OverflowError):
            return None

    return None


def stable_id(source: str, *parts: str) -> str:
    """A deterministic external_id for sources with no usable native identifier."""
    normalized = "|".join(normalize_space(p).lower() for p in parts if p)
    digest = hashlib.sha1(f"{source}|{normalized}".encode()).hexdigest()
    return digest[:16]


def guess_level(text: str) -> str:
    """Infer the study level from a title or eligibility blurb."""
    t = (text or "").lower()
    if re.search(r"\bph\.?\s?d\b|doctoral|doctorate|research fellow", t):
        return "phd"
    if re.search(r"\bpost[- ]?graduat|\bpg\b|\bm\.?\s?tech|\bm\.?\s?sc|\bmba\b|master", t):
        return "pg"
    if re.search(
        r"\bunder[- ]?graduat|\bug\b|\bb\.?\s?tech|\bb\.?\s?sc|\bb\.?\s?a\b"
        r"|\bb\.?\s?com|bachelor|degree|diploma|polytechnic",
        t,
    ):
        return "ug"
    if re.search(
        r"\bclass\s*(1[0-2]|[1-9])\b|\bschool\b|pre[- ]?matric|post[- ]?matric"
        r"|\bx\b\s*/\s*\bxii\b|secondary",
        t,
    ):
        return "school"
    return "any"


def infer_tags(text: str) -> list[str]:
    """Derive the dashboard's filter tags from free text."""
    t = (text or "").lower()
    tags: list[str] = []

    def add(tag: str, pattern: str) -> None:
        if re.search(pattern, t):
            tags.append(tag)

    add("girls", r"\bgirl|\bwomen\b|\bwoman\b|\bfemale\b|pragati|single girl")
    add("sc_st", r"\bsc\b|\bst\b|scheduled caste|scheduled tribe|\bsc/st\b|tribal")
    add("obc", r"\bobc\b|other backward|backward class")
    add("minority", r"\bminorit|muslim|christian|sikh|buddhist|jain|parsi")
    add("pwd", r"\bpwd\b|disabilit|differently abled|divyang|saksham|visually impaired")
    add("need", r"welfare based|need[- ]based|economically weaker|income|bpl|poor")
    add("merit", r"merit based|\bmerit\b|topper|top class|rank")
    add("renewal", r"\brenewal\b")
    add("technical", r"technical|engineering|polytechnic|aicte|\bb\.?\s?tech")
    add("research", r"research|fellowship|\bph\.?\s?d\b")
    return tags
