"""Regenerate backend/seed/scholarships.json from the live portals.

The seed is the curated fallback that keeps the dashboard populated when every
scraper fails (spec §7.5.5). Because it stores real deadlines, it goes stale:
once every seeded deadline has passed, the fallback shows nothing. Re-run this
script to refresh it:

    python -m backend.seed.generate_seed

It writes only scholarships that are still open on the day it runs, keeps the
NSP set diverse across level and audience tags, and never writes a record whose
apply_url lacks a path (the deep-link rule, spec §6).

Entries whose deadline could not be verified from an official source are given
`"deadline": null`: they stay visible in the dashboard and sort last, which is
honest about what is known rather than inventing a date.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from backend.scrapers.base import ScrapedScholarship, make_client
from backend.scrapers.buddy4study import Buddy4StudyScraper
from backend.scrapers.nsp import NspScraper
from backend.scrapers.vidyasaarathi import VidyasaarathiScraper

log = logging.getLogger("generate_seed")

OUT_PATH = Path(__file__).resolve().parent / "scholarships.json"

#: Private and corporate programmes whose official pages were checked by hand.
#: These carry no deadline unless it was confirmed on an official page, so they
#: remain visible instead of silently expiring.
CURATED: list[dict] = [
    {
        "source": "manual",
        "external_id": "manual-vidyadhan",
        "title": "Vidyadhan Scholarship (Sarojini Damodaran Foundation)",
        "provider": "Sarojini Damodaran Foundation",
        "description": (
            "State-wise scholarships for students who have cleared Class 10, "
            "continuing through graduation. Selection is by merit and need."
        ),
        "award_amount": "Varies by state and course",
        "eligibility": (
            "Students from low-income families who have completed Class 10 with "
            "strong marks. Separate state-wise programmes with their own cut-offs."
        ),
        "level": "school",
        "tags": ["need", "merit"],
        "deadline": None,
        "apply_url": "https://www.vidyadhan.org/apply",
        "info_url": "https://www.vidyadhan.org/apply",
    },
    {
        "source": "manual",
        "external_id": "manual-jn-tata-endowment",
        "title": "JN Tata Endowment Loan Scholarship",
        "provider": "JN Tata Endowment for the Higher Education of Indians",
        "description": (
            "Loan scholarship for Indian graduates pursuing postgraduate study "
            "abroad, awarded on academic record and interview."
        ),
        "award_amount": "Loan scholarship, amount set per awardee",
        "eligibility": (
            "Indian nationals with a first degree, applying for postgraduate "
            "study overseas."
        ),
        "level": "pg",
        "tags": ["merit"],
        "deadline": None,
        "apply_url": "https://www.jntataendowment.org/eligibility-criteria",
        "info_url": "https://www.jntataendowment.org/eligibility-criteria",
    },
    {
        "source": "manual",
        "external_id": "manual-inlaks-shivdasani",
        "title": "Inlaks Shivdasani Foundation Scholarships",
        "provider": "Inlaks Shivdasani Foundation",
        "description": (
            "Scholarships for Indian students taking up full-time postgraduate "
            "study at top universities in the US, UK and Europe."
        ),
        "award_amount": "Up to USD 100,000 (tuition, living and travel)",
        "eligibility": (
            "Indian citizens resident in India with a strong first degree, "
            "normally under 30 years of age."
        ),
        "level": "pg",
        "tags": ["merit"],
        "deadline": None,
        "apply_url": "https://www.inlaksfoundation.org/scholarships/",
        "info_url": "https://www.inlaksfoundation.org/scholarships/",
    },
    {
        "source": "manual",
        "external_id": "manual-aditya-birla-scholarship",
        "title": "Aditya Birla Scholarship",
        "provider": "Aditya Birla Group",
        "description": (
            "Scholarships for students at select IITs, IIMs, BITS Pilani, XLRI "
            "and national law schools."
        ),
        "award_amount": "Varies by institute",
        "eligibility": (
            "Students admitted to one of the partner institutes; selection is "
            "by academic record and interview."
        ),
        "level": "pg",
        "tags": ["merit"],
        "deadline": None,
        "apply_url": "https://www.adityabirlascholars.net/the-scholarship/",
        "info_url": "https://www.adityabirlascholars.net/the-scholarship/",
    },
    {
        "source": "manual",
        "external_id": "manual-sitaram-jindal",
        "title": "Sitaram Jindal Foundation Scholarship",
        "provider": "Sitaram Jindal Foundation",
        "description": (
            "Monthly scholarships across several categories, from Class 11 "
            "through professional and postgraduate courses."
        ),
        "award_amount": "INR 500 to INR 2,500 per month by category",
        "eligibility": (
            "Students in India meeting the per-category marks and income "
            "criteria set out in the foundation's scheme table."
        ),
        "level": "any",
        "tags": ["need", "merit"],
        "deadline": None,
        "apply_url": "https://www.sitaramjindalfoundation.org/scholarships.php",
        "info_url": "https://www.sitaramjindalfoundation.org/scholarships.php",
    },
]

#: Tags we want represented in the NSP slice of the seed.
_WANTED_TAGS = ("girls", "pwd", "sc_st", "obc", "minority", "merit", "need", "research")


def _diverse_nsp(records: list[ScrapedScholarship], limit: int) -> list[ScrapedScholarship]:
    """Pick a spread of NSP schemes across audience tags and study levels."""
    chosen: list[ScrapedScholarship] = []
    seen: set[str] = set()

    def take(record: ScrapedScholarship) -> None:
        if record.external_id not in seen:
            seen.add(record.external_id)
            chosen.append(record)

    # One per audience tag first, then one per level, then fill by deadline.
    for tag in _WANTED_TAGS:
        for record in records:
            if tag in record.tags:
                take(record)
                break
    for level in ("school", "ug", "pg", "phd", "any"):
        for record in records:
            if record.level == level:
                take(record)
                break
    for record in sorted(records, key=lambda r: (r.deadline or date.max)):
        if len(chosen) >= limit:
            break
        take(record)

    return chosen[:limit]


def _to_json(record: ScrapedScholarship) -> dict:
    raw = asdict(record)
    raw["deadline"] = record.deadline.isoformat() if record.deadline else None
    raw["opens_at"] = record.opens_at.isoformat() if record.opens_at else None
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nsp-limit", type=int, default=18, help="how many NSP schemes to keep"
    )
    parser.add_argument(
        "--b4s-pages",
        type=int,
        default=120,
        help="how many Buddy4Study pages to crawl (run offline, so be generous)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    today = date.today()
    entries: list[dict] = []

    with make_client() as client:
        try:
            nsp = [r for r in NspScraper().fetch(client) if (r.deadline or date.max) >= today]
            log.info("nsp: %s open schemes", len(nsp))
            entries += [_to_json(r) for r in _diverse_nsp(nsp, args.nsp_limit)]
        except Exception:
            log.exception("nsp fetch failed; seeding without it")

        try:
            b4s = Buddy4StudyScraper(max_pages=args.b4s_pages).fetch(client)
            log.info("buddy4study: %s open scholarships", len(b4s))
            entries += [_to_json(r) for r in b4s]
        except Exception:
            log.exception("buddy4study fetch failed; seeding without it")

        try:
            vs = VidyasaarathiScraper().fetch(client)
            log.info("vidyasaarathi: %s open schemes", len(vs))
            entries += [_to_json(r) for r in vs]
        except Exception:
            log.exception("vidyasaarathi fetch failed; seeding without it")

    entries += CURATED

    # Enforce the deep-link rule here too (spec §6): a URL with no path would be
    # skipped by the seed loader anyway, so never write one to the file.
    kept: list[dict] = []
    for entry in entries:
        url = entry.get("apply_url") or ""
        path = url.split("://", 1)[-1].partition("/")[2].strip("/")
        if not path:
            log.error(
                "dropping %r: apply_url %r has no path, so it is a portal homepage",
                entry.get("title"),
                url,
            )
            continue
        kept.append(entry)
    entries = kept

    # Deadline first, undated last, matching how the dashboard sorts.
    entries.sort(key=lambda e: (e.get("deadline") is None, e.get("deadline") or ""))

    payload = {
        "_meta": {
            "generated_on": today.isoformat(),
            "generated_by": "python -m backend.seed.generate_seed",
            "note": (
                "Curated fallback loaded only when the scholarships table is "
                "empty. Real deadlines go stale: regenerate this file when the "
                "dated entries have passed. Entries with a null deadline were "
                "verified to exist but had no deadline confirmable from an "
                "official page, so none was invented."
            ),
            "counts": {},
        },
        "scholarships": entries,
    }
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["source"]] = counts.get(entry["source"], 0) + 1
    payload["_meta"]["counts"] = counts

    OUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    log.info("wrote %s entries to %s (%s)", len(entries), OUT_PATH, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
