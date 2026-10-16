"""Scholarship discovery endpoints.

The list is always ordered by nearest deadline with undated rows last (spec §8),
and each item carries the caller's tracked status so the dashboard needs one call.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.db import get_db
from backend.models import Application, RefreshRun, Scholarship, User
from backend.schemas import (
    ScholarshipListOut,
    ScholarshipMetaOut,
    ScholarshipOut,
    SourceCount,
)

router = APIRouter(prefix="/scholarships", tags=["scholarships"])


def _days_left(deadline: date | None, today: date) -> int | None:
    return None if deadline is None else (deadline - today).days


def _apply_order(stmt: Select) -> Select:
    """deadline ASC NULLS LAST, portably.

    SQLite has no NULLS LAST, so sort on a computed "is null" flag first.
    """
    return stmt.order_by(
        case((Scholarship.deadline.is_(None), 1), else_=0).asc(),
        Scholarship.deadline.asc(),
        Scholarship.id.asc(),
    )


def _serialize(
    row: Scholarship, today: date, tracked: dict[int, Application]
) -> ScholarshipOut:
    out = ScholarshipOut.model_validate(row)
    out.days_left = _days_left(row.deadline, today)
    app = tracked.get(row.id)
    if app is not None:
        out.application_status = app.status
        out.application_id = app.id
    return out


def _tracked_for(db: Session, user: User, ids: list[int]) -> dict[int, Application]:
    if not ids:
        return {}
    rows = db.execute(
        select(Application).where(
            Application.user_id == user.id, Application.scholarship_id.in_(ids)
        )
    ).scalars()
    return {a.scholarship_id: a for a in rows}


@router.get("", response_model=ScholarshipListOut)
def list_scholarships(
    q: str | None = Query(default=None, max_length=200, description="Free-text search"),
    source: str | None = Query(default=None, max_length=32),
    level: str | None = Query(default=None, max_length=16),
    tag: list[str] | None = Query(default=None, description="Repeatable; matches ALL given tags"),
    include_expired: bool = Query(default=False),
    due_within_days: int | None = Query(default=None, ge=0, le=3650),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScholarshipListOut:
    today = date.today()
    stmt = select(Scholarship)

    if not include_expired:
        # Hide deactivated rows and anything already past its deadline. The
        # date check is belt-and-braces: ingest also flips is_active, but a row
        # can expire between two daily runs.
        stmt = stmt.where(
            Scholarship.is_active.is_(True),
            or_(Scholarship.deadline.is_(None), Scholarship.deadline >= today),
        )

    if source:
        stmt = stmt.where(Scholarship.source == source.lower())
    if level:
        stmt = stmt.where(Scholarship.level == level.lower())

    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Scholarship.title).like(needle),
                func.lower(func.coalesce(Scholarship.provider, "")).like(needle),
                func.lower(func.coalesce(Scholarship.description, "")).like(needle),
                func.lower(func.coalesce(Scholarship.eligibility, "")).like(needle),
            )
        )

    if due_within_days is not None:
        cutoff = today + timedelta(days=due_within_days)
        # An undated scholarship has no known due date, so it cannot satisfy
        # "closing within N days" and is excluded here.
        stmt = stmt.where(
            Scholarship.deadline.is_not(None),
            Scholarship.deadline >= today,
            Scholarship.deadline <= cutoff,
        )

    wanted_tags = {t.strip().lower() for t in (tag or []) if t.strip()}

    if wanted_tags:
        # tags is a JSON column, so match in Python rather than with a
        # dialect-specific JSON operator. This has to happen before paging:
        # filtering an already-limited page would drop matches that sit beyond
        # it and report a wrong total. The catalogue is hundreds of rows, so
        # ordering it in SQL and slicing here is cheap.
        matched = [
            row
            for row in db.execute(_apply_order(stmt)).scalars()
            if wanted_tags.issubset({t.lower() for t in (row.tags or [])})
        ]
        total = len(matched)
        rows = matched[offset : offset + limit]
    else:
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = list(db.execute(_apply_order(stmt).limit(limit).offset(offset)).scalars())

    tracked = _tracked_for(db, user, [r.id for r in rows])
    return ScholarshipListOut(
        items=[_serialize(r, today, tracked) for r in rows], total=total
    )


@router.get("/meta", response_model=ScholarshipMetaOut)
def scholarship_meta(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScholarshipMetaOut:
    today = date.today()
    open_filter = (
        Scholarship.is_active.is_(True),
        or_(Scholarship.deadline.is_(None), Scholarship.deadline >= today),
    )

    sources = [
        SourceCount(source=s, count=c)
        for s, c in db.execute(
            select(Scholarship.source, func.count())
            .where(*open_filter)
            .group_by(Scholarship.source)
            .order_by(func.count().desc())
        ).all()
    ]
    levels = [
        SourceCount(source=lv, count=c)
        for lv, c in db.execute(
            select(Scholarship.level, func.count())
            .where(*open_filter)
            .group_by(Scholarship.level)
            .order_by(func.count().desc())
        ).all()
    ]

    tag_counter: Counter[str] = Counter()
    for (tags,) in db.execute(select(Scholarship.tags).where(*open_filter)).all():
        for t in tags or []:
            tag_counter[t.lower()] += 1

    total_active = db.execute(
        select(func.count()).select_from(Scholarship).where(*open_filter)
    ).scalar_one()

    closing_this_week = db.execute(
        select(func.count())
        .select_from(Scholarship)
        .where(
            Scholarship.is_active.is_(True),
            Scholarship.deadline.is_not(None),
            Scholarship.deadline >= today,
            Scholarship.deadline <= today + timedelta(days=7),
        )
    ).scalar_one()

    expired_hidden = db.execute(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.deadline.is_not(None), Scholarship.deadline < today)
    ).scalar_one()

    last_run = db.execute(
        select(RefreshRun).order_by(RefreshRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    return ScholarshipMetaOut(
        sources=sources,
        levels=levels,
        tags=[SourceCount(source=t, count=c) for t, c in tag_counter.most_common()],
        total_active=total_active,
        closing_this_week=closing_this_week,
        expired_hidden=expired_hidden,
        last_refresh_at=(last_run.finished_at or last_run.started_at) if last_run else None,
        last_refresh_summary=last_run.summary if last_run else {},
    )


@router.get("/{scholarship_id}", response_model=ScholarshipOut)
def get_scholarship(
    scholarship_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScholarshipOut:
    row = db.get(Scholarship, scholarship_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found"
        )
    tracked = _tracked_for(db, user, [row.id])
    return _serialize(row, date.today(), tracked)
