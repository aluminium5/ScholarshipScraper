"""Ingest service: run the scrapers, upsert, expire, and record the run (spec §7.5).

The guiding rule is that a refresh must never make the dashboard worse. A
scraper that throws, times out, or returns nothing leaves its existing rows
exactly as they were; only a source that actually returned records is allowed to
deactivate its own stale rows.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.models import RefreshRun, Scholarship
from backend.scrapers.base import ScrapedScholarship, make_client
from backend.scrapers.registry import ACTIVE_SCRAPERS

log = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "scholarships.json"

# Fields copied from a scraped record onto a Scholarship row.
_SYNCED_FIELDS = (
    "title",
    "provider",
    "description",
    "award_amount",
    "eligibility",
    "level",
    "tags",
    "opens_at",
    "deadline",
    "apply_url",
    "info_url",
)


@dataclass
class SourceResult:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "inserted": self.inserted,
            "updated": self.updated,
            "deactivated": self.deactivated,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def _is_portal_homepage(url: str) -> bool:
    """Reject a URL with no path: the deep-link rule (spec §6).

    NSP's /ApplicationForm/ has a path, so it passes; a bare domain does not.
    """
    stripped = url.split("?")[0].split("#")[0]
    without_scheme = stripped.split("://", 1)[-1]
    path = without_scheme.partition("/")[2].strip("/")
    return path == ""


def _upsert(db: Session, record: ScrapedScholarship, result: SourceResult) -> int | None:
    """Insert or update one scraped record. Returns the row id, or None if skipped."""
    if not record.apply_url or _is_portal_homepage(record.apply_url):
        log.warning(
            "%s: skipping %r - apply_url %r is not scholarship-specific",
            record.source,
            record.title,
            record.apply_url,
        )
        result.skipped += 1
        return None

    now = datetime.now(timezone.utc)
    row = db.execute(
        select(Scholarship).where(
            Scholarship.source == record.source,
            Scholarship.external_id == record.external_id,
        )
    ).scalar_one_or_none()

    if row is None:
        row = Scholarship(
            source=record.source,
            external_id=record.external_id,
            **{f: getattr(record, f) for f in _SYNCED_FIELDS},
            is_active=True,
            last_seen_at=now,
        )
        db.add(row)
        db.flush()
        result.inserted += 1
        return row.id

    for name in _SYNCED_FIELDS:
        incoming = getattr(record, name)
        # Don't let a thinner re-scrape blank out a field we already have.
        if incoming in (None, "", []) and getattr(row, name) not in (None, "", []):
            continue
        setattr(row, name, incoming)

    row.is_active = True
    row.last_seen_at = now
    db.flush()
    result.updated += 1
    return row.id


def _deactivate_unseen(
    db: Session, source: str, seen_ids: set[int], result: SourceResult
) -> None:
    """Deactivate this source's rows that this run did not see.

    Only called for a source that returned at least one record, so a broken
    scraper can never wipe its source (spec §7.5.3).
    """
    stmt = (
        update(Scholarship)
        .where(Scholarship.source == source, Scholarship.is_active.is_(True))
        .values(is_active=False)
    )
    if seen_ids:
        stmt = stmt.where(Scholarship.id.notin_(seen_ids))
    result.deactivated = db.execute(stmt).rowcount or 0


def _expire_past_deadlines(db: Session, today: date) -> int:
    """Any active row whose deadline has passed is no longer open (spec §7.5.4)."""
    return (
        db.execute(
            update(Scholarship)
            .where(
                Scholarship.is_active.is_(True),
                Scholarship.deadline.is_not(None),
                Scholarship.deadline < today,
            )
            .values(is_active=False)
        ).rowcount
        or 0
    )


def load_seed_if_empty(db: Session) -> int:
    """Load the curated fallback when there are no scholarships at all (spec §7.5.5).

    This is what keeps the dashboard populated if every scraper fails.
    """
    existing = db.execute(select(Scholarship.id).limit(1)).scalar_one_or_none()
    if existing is not None:
        return 0

    if not SEED_PATH.exists():
        log.warning("seed file missing at %s", SEED_PATH)
        return 0

    try:
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.error("could not read seed file: %s", exc)
        return 0

    records = payload.get("scholarships", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        log.error("seed file has an unexpected shape")
        return 0

    now = datetime.now(timezone.utc)
    inserted = 0
    for raw in records:
        if not isinstance(raw, dict):
            continue
        apply_url = (raw.get("apply_url") or "").strip()
        if not apply_url or _is_portal_homepage(apply_url):
            log.warning("seed: skipping %r - apply_url is not specific", raw.get("title"))
            continue

        source = (raw.get("source") or "manual").strip().lower()
        external_id = str(raw.get("external_id") or "").strip()
        if not external_id or not raw.get("title"):
            continue

        if db.execute(
            select(Scholarship.id).where(
                Scholarship.source == source, Scholarship.external_id == external_id
            )
        ).scalar_one_or_none():
            continue

        def _as_date(value: Any) -> date | None:
            if not value:
                return None
            try:
                return date.fromisoformat(str(value))
            except ValueError:
                log.warning("seed: bad date %r on %r", value, raw.get("title"))
                return None

        db.add(
            Scholarship(
                source=source,
                external_id=external_id,
                title=str(raw["title"]).strip(),
                provider=raw.get("provider"),
                description=raw.get("description"),
                award_amount=raw.get("award_amount"),
                eligibility=raw.get("eligibility"),
                level=raw.get("level") or "any",
                tags=raw.get("tags") or [],
                opens_at=_as_date(raw.get("opens_at")),
                deadline=_as_date(raw.get("deadline")),
                apply_url=apply_url,
                info_url=raw.get("info_url"),
                is_active=True,
                last_seen_at=now,
            )
        )
        inserted += 1

    db.commit()
    log.info("seed: inserted %s scholarships", inserted)
    return inserted


def run_ingest(db: Session, trigger: str = "cron") -> RefreshRun:
    """Run every scraper and reconcile the database. Always records a RefreshRun."""
    started = datetime.now(timezone.utc)
    run = RefreshRun(started_at=started, trigger=trigger, ok=True, summary={})
    db.add(run)
    db.commit()

    summary: dict[str, Any] = {}
    any_error = False

    with make_client() as client:
        for scraper in ACTIVE_SCRAPERS:
            result = SourceResult()
            records: list[ScrapedScholarship] = []
            try:
                records = scraper.fetch(client)
                result.fetched = len(records)
            except Exception as exc:  # noqa: BLE001 - one scraper must not stop the run
                any_error = True
                result.errors.append(f"{type(exc).__name__}: {exc}")
                log.exception("%s: fetch failed", scraper.source)

            if result.errors:
                # Leave this source's rows untouched (spec §7.5.3).
                summary[scraper.source] = result.as_dict()
                continue

            seen_ids: set[int] = set()
            try:
                for record in records:
                    row_id = _upsert(db, record, result)
                    if row_id is not None:
                        seen_ids.add(row_id)

                # Only a source that actually returned records may retire its
                # own stale rows.
                if result.fetched > 0:
                    _deactivate_unseen(db, scraper.source, seen_ids, result)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                any_error = True
                result.errors.append(f"persist failed: {type(exc).__name__}: {exc}")
                log.exception("%s: persisting records failed", scraper.source)

            summary[scraper.source] = result.as_dict()

    # Expiry and the seed fallback apply regardless of scraper outcomes.
    try:
        expired = _expire_past_deadlines(db, date.today())
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        expired = 0
        any_error = True
        log.exception("expiring past deadlines failed: %s", exc)

    seeded = 0
    try:
        seeded = load_seed_if_empty(db)
    except Exception:  # noqa: BLE001
        db.rollback()
        any_error = True
        log.exception("loading seed data failed")

    summary["_totals"] = {
        "expired": expired,
        "seeded": seeded,
        "sources_with_errors": sorted(
            s for s, v in summary.items() if isinstance(v, dict) and v.get("errors")
        ),
    }

    run.finished_at = datetime.now(timezone.utc)
    run.ok = not any_error
    run.summary = summary
    db.commit()
    db.refresh(run)

    log.info("refresh finished ok=%s summary=%s", run.ok, summary)
    return run
