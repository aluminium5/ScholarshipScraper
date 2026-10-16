"""The scrapers the ingest service runs (spec §7, registry.py).

Order matters only for log readability. Each scraper is isolated by the ingest
service, so an unverified or broken one cannot affect the others.
"""

from __future__ import annotations

from backend.scrapers.base import BaseScraper
from backend.scrapers.buddy4study import Buddy4StudyScraper
from backend.scrapers.nsp import NspScraper
from backend.scrapers.vidyasaarathi import VidyasaarathiScraper

ACTIVE_SCRAPERS: list[BaseScraper] = [
    NspScraper(),            # verified against a saved fixture
    Buddy4StudyScraper(),    # needs LISTING_ENDPOINT; returns [] until then
    VidyasaarathiScraper(),  # unverified: host unreachable from dev machine
]

#: Sources the app knows about, including those that only ever come from seed data.
KNOWN_SOURCES = ("nsp", "buddy4study", "vidyasaarathi", "manual")


def scraper_sources() -> list[str]:
    return [s.source for s in ACTIVE_SCRAPERS]
