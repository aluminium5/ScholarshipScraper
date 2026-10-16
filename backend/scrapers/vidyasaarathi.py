"""Vidyasaarathi scraper (spec §7.3).

STATUS: UNVERIFIED. The host refused every connection from the development
machine on 17 Oct 2026 (TLS reset, not an HTTP error), so the live markup could
not be inspected and there is no HTML fixture. The selectors below follow the
structure described in the spec and are deliberately defensive: anything that
does not yield a scholarship-specific detail link is skipped.

The spec also records that on 16 Oct 2026 the "Open Schemes" tab read
"Currently No Schemes are Available." An empty list is therefore an expected,
non-error outcome and must return [] quietly.

Verify after deploying (Vercel egress differs from a home connection):
    GET /api/cron/refresh  ->  check summary["vidyasaarathi"]["errors"]
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

BASE_URL = "https://www.vidyasaarathi.co.in"
LIST_URL = f"{BASE_URL}/Vidyasaarathi/scholarship"

_EMPTY_MARKERS = (
    "currently no schemes are available",
    "no schemes are available",
    "no scheme available",
    "no records found",
)

_DEADLINE_LABEL = re.compile(
    r"(?:last date|closing date|apply before|last day|end date)\s*:?\s*"
    r"([0-3]?\d[-/.][01]?\d[-/.]\d{4}|[0-3]?\d\s+[A-Za-z]{3,9},?\s+\d{4})",
    re.IGNORECASE,
)
_OPENS_LABEL = re.compile(
    r"(?:start date|opens? on|start)\s*:?\s*"
    r"([0-3]?\d[-/.][01]?\d[-/.]\d{4}|[0-3]?\d\s+[A-Za-z]{3,9},?\s+\d{4})",
    re.IGNORECASE,
)
_AWARD_LABEL = re.compile(
    r"(?:amount|award|scholarship value|benefit)\s*:?\s*"
    r"((?:rs\.?|inr|₹)\s*[\d,]+(?:\s*(?:lakh|lakhs|crore|per annum|p\.a\.?))?)",
    re.IGNORECASE,
)

# A detail URL must look scheme-specific; a bare listing/home path is rejected.
_DETAIL_HINTS = ("scheme", "scholarship", "detail", "apply", "program")
_NON_DETAIL = {
    "/vidyasaarathi/scholarship",
    "/vidyasaarathi/scholarship/",
    "/vidyasaarathi",
    "/vidyasaarathi/",
    "/",
}


def _absolute(href: str) -> str:
    if href.startswith(("http://", "https://")):
        return href
    return f"{BASE_URL}/{href.lstrip('/')}"


def _is_detail_link(href: str | None) -> bool:
    """True only for a link that plausibly points at one scheme."""
    if not href:
        return False
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return False

    path = re.sub(r"^https?://[^/]+", "", href).split("?")[0].split("#")[0]
    if path.lower().rstrip("/") in {p.rstrip("/") for p in _NON_DETAIL}:
        return False
    lowered = href.lower()
    if not any(h in lowered for h in _DETAIL_HINTS):
        return False
    # Require something that distinguishes one scheme: an id, a query arg or a
    # deeper path segment than the listing itself.
    return bool(
        re.search(r"\d", path) or "?" in href or path.count("/") >= 3
    )


def _card_title(card: Tag) -> str | None:
    for selector in ("h1", "h2", "h3", "h4", "h5", "h6", ".scheme-name", ".card-title"):
        node = card.select_one(selector)
        if node is not None:
            text = normalize_space(node.get_text(" ", strip=True))
            if len(text) >= 8:
                return text
    # Fall back to the anchor's own text.
    link = card.find("a", href=True)
    if link is not None:
        text = normalize_space(link.get_text(" ", strip=True))
        if len(text) >= 8:
            return text
    return None


def parse_vidyasaarathi_html(html: str) -> list[ScrapedScholarship]:
    """Parse the Open Schemes listing. Returns [] when no schemes are listed."""
    soup = BeautifulSoup(html, "lxml")

    page_text = normalize_space(soup.get_text(" ", strip=True)).lower()
    if any(marker in page_text for marker in _EMPTY_MARKERS):
        log.info("vidyasaarathi: portal reports no open schemes")
        return []

    # Candidate cards: any container holding a plausible scheme detail link.
    candidates: list[Tag] = []
    for link in soup.find_all("a", href=True):
        if not _is_detail_link(link.get("href")):
            continue
        container = link
        for _ in range(4):
            parent = container.parent
            if not isinstance(parent, Tag):
                break
            container = parent
            classes = " ".join(parent.get("class") or []).lower()
            if any(c in classes for c in ("card", "scheme", "panel", "item", "row")):
                break
        if container not in candidates:
            candidates.append(container)

    results: list[ScrapedScholarship] = []
    seen: set[str] = set()

    for card in candidates:
        link = next(
            (a for a in card.find_all("a", href=True) if _is_detail_link(a["href"])),
            None,
        )
        if link is None:
            continue

        title = _card_title(card)
        if not title:
            continue

        apply_url = _absolute(link["href"].strip())
        text = normalize_space(card.get_text(" ", strip=True))

        deadline_match = _DEADLINE_LABEL.search(text)
        opens_match = _OPENS_LABEL.search(text)
        award_match = _AWARD_LABEL.search(text)

        external_id = stable_id("vidyasaarathi", title)
        if external_id in seen:
            continue
        seen.add(external_id)

        results.append(
            ScrapedScholarship(
                source="vidyasaarathi",
                external_id=external_id,
                title=title,
                # The sponsoring company is the useful provider here, but the
                # markup is unconfirmed, so leave it unset rather than guess.
                provider=None,
                apply_url=apply_url,
                info_url=apply_url,
                deadline=parse_date(deadline_match.group(1)) if deadline_match else None,
                opens_at=parse_date(opens_match.group(1)) if opens_match else None,
                award_amount=(
                    normalize_space(award_match.group(1))[:300] if award_match else None
                ),
                level=guess_level(f"{title} {text}"),
                tags=infer_tags(f"{title} {text}"),
                description=(
                    "Corporate-funded scholarship listed on Vidyasaarathi. "
                    "Applying requires a Vidyasaarathi login."
                ),
            )
        )

    log.info("vidyasaarathi: parsed %s schemes", len(results))
    return results


class VidyasaarathiScraper(BaseScraper):
    source = "vidyasaarathi"
    verified = False

    def fetch(self, client: httpx.Client) -> list[ScrapedScholarship]:
        response = get_with_retries(client, LIST_URL)
        response.encoding = response.encoding or "utf-8"
        return parse_vidyasaarathi_html(response.text)
