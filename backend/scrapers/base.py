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


_LEVEL_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "phd",
        r"\bph\.?\s?d\b|doctoral|doctorate|post[- ]?doc"
        # JRF and SRF are doctoral-level awards.
        r"|(?:junior|senior) research fellow",
    ),
    (
        "pg",
        r"\bpost[- ]?graduat|\bpg\b|\bm\.?\s?tech\b|\bm\.?\s?sc\b|\bm\.?\s?a\b"
        r"|\bmba\b|\bmaster",
    ),
    (
        "ug",
        r"\bunder[- ]?graduat|\bug\b|\bb\.?\s?tech\b|\bb\.?\s?sc\b|\bb\.?\s?a\b"
        r"|\bb\.?\s?com\b|bachelor|\bdegree\b|diploma|polytechnic|\biti\b",
    ),
    (
        "school",
        r"\bclass\s*(?:1[0-2]|[1-9])\b|\bschool\b|pre[- ]?matric|post[- ]?matric"
        r"|\bsecondary\b|\bxii\b|\bclass\s*x\b",
    ),
)


def guess_level(text: str) -> str:
    """Infer the study level from a title or eligibility blurb.

    Whichever level is mentioned first wins. Callers pass the title ahead of the
    eligibility text, so the programme's own wording decides, and an aside like
    "integrated master's" later in the criteria cannot override an
    "undergraduate" in the title.
    """
    t = (text or "").lower()
    best: tuple[int, str] | None = None
    for level, pattern in _LEVEL_PATTERNS:
        match = re.search(pattern, t)
        if match is not None and (best is None or match.start() < best[0]):
            best = (match.start(), level)
    return best[1] if best else "any"


#: Tags describing who a scholarship is *for*. Inferred from the title only:
#: eligibility prose routinely names every category it does not serve.
_AUDIENCE_TAGS: tuple[tuple[str, str], ...] = (
    ("girls", r"\bgirls?\b|\bwomen\b|\bwoman\b|\bfemale\b|\bkanya\b|\bpragati\b"),
    (
        "sc_st",
        r"scheduled caste|scheduled tribe|\bsc\s*/\s*st\b|\btribal\b"
        # Bare SC/ST abbreviations, but not the "Sc" of B.Sc or M.Sc.
        r"|(?<![.a-z])\bscs?\b|(?<![.a-z])\bsts?\b",
    ),
    ("obc", r"\bobcs?\b|other backward|backward class"),
    ("minority", r"\bminorit|\bmuslim|\bchristian|\bsikh\b|\bbuddhist|\bjain\b|\bparsi"),
    (
        "pwd",
        r"\bpwd\b|disabilit|differently abled|divyang|specially abled"
        r"|visually impaired|\bsaksham\b",
    ),
)

#: Tags describing the nature of the award; safe to read from the whole blurb.
_NATURE_TAGS: tuple[tuple[str, str], ...] = (
    ("need", r"welfare based|need[- ]based|economically weaker|\bincome\b|\bbpl\b"),
    ("merit", r"merit based|\bmerit\b|\btopper|top class|\brank\b"),
    ("renewal", r"\brenewal\b"),
    ("technical", r"\btechnical\b|engineering|polytechnic|\baicte\b|\bb\.?\s?tech\b"),
    ("research", r"\bresearch\b|\bfellowship\b|\bph\.?\s?d\b"),
)


def infer_tags(title: str, detail: str | None = None) -> list[str]:
    """Derive the dashboard's filter tags.

    `title` decides the audience tags; `detail` (eligibility, description) only
    contributes to the award-nature tags. Lumping both together tags almost
    every scholarship with every category, which makes the filter chips useless.
    """
    title_text = (title or "").lower()
    all_text = f"{title or ''} {detail or ''}".lower()

    tags: list[str] = []
    for tag, pattern in _AUDIENCE_TAGS:
        if re.search(pattern, title_text):
            tags.append(tag)
    for tag, pattern in _NATURE_TAGS:
        if re.search(pattern, all_text):
            tags.append(tag)
    return tags
