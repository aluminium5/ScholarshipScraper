"""National Scholarship Portal scraper (spec §7.1).

The All-Scholarships page is server-rendered, so a plain GET is enough. Verified
against the live page on 16 Oct 2026; that HTML is kept as a test fixture at
backend/tests/fixtures/nsp.html.

Page shape:

    div.accordion-item
      h7.accordion-header > button      -> ministry name (provider)
      div.accordion-body
        div.row                          -> one scheme
          div.col-md-10
            h6                           -> scheme title
            span ... "Scheme  Open from : 01-06-2026"
            span ... "Student Application  Open till : 31-10-2026"
            div.mb-4 > a[Specifications], a[FAQ]

Note the doubled spaces inside the labels: all label matching goes through
normalize_space first.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup, Tag

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

LIST_URL = "https://scholarships.gov.in/All-Scholarships"

# NSP has no public per-scheme page: you pick the scheme after an OTR login.
# This is the closest legitimate deep link (spec §6), and the UI shows a note
# telling the student which scheme to select.
APPLY_URL = "https://scholarships.gov.in/ApplicationForm/"

# Links the portal renders when a document is missing.
_DEAD_LINK_SUFFIXES = ("/null", "/null/", "#", "javascript:void(0)")

_DEADLINE_LABEL = re.compile(
    r"Student Application\s*Open till(?:\s*\(for Renewal\))?\s*:?\s*([0-9][0-9/.\-]{5,})",
    re.IGNORECASE,
)
_OPENS_LABEL = re.compile(
    r"Scheme\s*Open from(?:\s*\(for Renewal\))?\s*:?\s*([0-9][0-9/.\-]{5,})",
    re.IGNORECASE,
)
_RENEWAL_LABEL = re.compile(r"\(for Renewal\)", re.IGNORECASE)


def _is_usable_link(href: str | None) -> bool:
    if not href:
        return False
    href = href.strip()
    if not href or href.lower().startswith("javascript:"):
        return False
    return not any(href.rstrip().endswith(s) for s in _DEAD_LINK_SUFFIXES)


def _ministry_for(block: Tag) -> str | None:
    """Walk up to the enclosing accordion item and read its header button."""
    for parent in block.parents:
        if not isinstance(parent, Tag):
            continue
        classes = parent.get("class") or []
        if "accordion-item" not in classes:
            continue
        # h7 is not a real HTML element, so match the class rather than the tag.
        header = parent.find(class_="accordion-header")
        if header is not None:
            button = header.find("button")
            text = normalize_space((button or header).get_text(" ", strip=True))
            if text:
                return text
    return None


def _clean_title(raw: str) -> str:
    title = normalize_space(raw)
    # Strip the trailing scheme-type marker; it is captured as a tag instead.
    return re.sub(
        r"\s*\((?:Merit|Welfare)\s+Based\s+Scheme\)\s*$", "", title, flags=re.IGNORECASE
    ).strip()


def parse_nsp_html(html: str) -> list[ScrapedScholarship]:
    """Parse the All-Scholarships listing. Pure function, unit-tested on a fixture."""
    soup = BeautifulSoup(html, "lxml")
    results: list[ScrapedScholarship] = []
    seen: set[str] = set()

    for heading in soup.find_all("h6"):
        raw_title = normalize_space(heading.get_text(" ", strip=True))
        # The page chrome reuses h6 (e.g. the "Academic Year 2026-27" banner),
        # so ignore headings that are not inside a scheme row.
        block = heading.find_parent(class_="col-md-10")
        if block is None or not raw_title:
            continue

        title = _clean_title(raw_title)
        if len(title) < 8:
            continue

        text = normalize_space(block.get_text(" ", strip=True))

        deadline_match = _DEADLINE_LABEL.search(text)
        deadline = parse_date(deadline_match.group(1)) if deadline_match else None
        opens_match = _OPENS_LABEL.search(text)
        opens_at = parse_date(opens_match.group(1)) if opens_match else None

        info_url: str | None = None
        for link in block.find_all("a"):
            label = normalize_space(link.get_text(" ", strip=True)).lower()
            href = link.get("href")
            if label.startswith("specification") and _is_usable_link(href):
                info_url = href.strip()
                break

        tags = infer_tags(f"{raw_title} {text}")
        lowered = raw_title.lower()
        if "merit based scheme" in lowered and "merit" not in tags:
            tags.append("merit")
        if "welfare based scheme" in lowered and "need" not in tags:
            tags.append("need")
        # A renewal-only scheme accepts no fresh applications this cycle.
        if _RENEWAL_LABEL.search(text) and "renewal" not in tags:
            tags.append("renewal")

        # Guideline PDF filenames change every academic year, so hash the title:
        # that keeps (source, external_id) stable across refreshes.
        external_id = stable_id("nsp", title)
        if external_id in seen:
            continue
        seen.add(external_id)

        results.append(
            ScrapedScholarship(
                source="nsp",
                external_id=external_id,
                title=title,
                provider=_ministry_for(block),
                apply_url=APPLY_URL,
                info_url=info_url,
                deadline=deadline,
                opens_at=opens_at,
                level=guess_level(raw_title),
                tags=tags,
                description=(
                    "Central government scholarship listed on the National "
                    "Scholarship Portal. Apply through NSP after One Time "
                    "Registration (OTR), then select this scheme."
                ),
            )
        )

    return results


class NspScraper(BaseScraper):
    source = "nsp"
    verified = True

    def fetch(self, client: httpx.Client) -> list[ScrapedScholarship]:
        response = get_with_retries(client, LIST_URL)
        # NSP serves this page as text/plain with no charset, so pin UTF-8
        # rather than let httpx guess (the titles contain en-dashes).
        response.encoding = "utf-8"
        records = parse_nsp_html(response.text)
        log.info("nsp: parsed %s schemes", len(records))
        return records
