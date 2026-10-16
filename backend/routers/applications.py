"""The application tracker: Saved -> Applied -> Under review -> Awarded / Rejected."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.auth import get_current_user
from backend.db import get_db
from backend.models import Application, Scholarship, User
from backend.schemas import (
    ApplicationIn,
    ApplicationOut,
    ApplicationPatch,
    ScholarshipOut,
)

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_out(row: Application, today: date | None = None) -> ApplicationOut:
    today = today or date.today()
    out = ApplicationOut.model_validate(row)
    if row.scholarship is not None:
        sch = ScholarshipOut.model_validate(row.scholarship)
        sch.days_left = (
            None
            if row.scholarship.deadline is None
            else (row.scholarship.deadline - today).days
        )
        sch.application_status = row.status
        sch.application_id = row.id
        out.scholarship = sch
    return out


def _owned(db: Session, user: User, application_id: int) -> Application:
    row = db.get(Application, application_id)
    # Same 404 for "missing" and "someone else's" so IDs cannot be probed.
    if row is None or row.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )
    return row


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ApplicationOut]:
    rows = db.execute(
        select(Application)
        .where(Application.user_id == user.id)
        .options(selectinload(Application.scholarship))
        .order_by(Application.updated_at.desc())
    ).scalars()
    today = date.today()
    return [_to_out(r, today) for r in rows]


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def upsert_application(
    payload: ApplicationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationOut:
    """Create or update the caller's tracker entry for one scholarship.

    The dashboard's Apply button calls this with status "saved" (spec §6), so it
    must be safe to call repeatedly for the same scholarship.
    """
    if db.get(Scholarship, payload.scholarship_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found"
        )

    row = db.execute(
        select(Application).where(
            Application.user_id == user.id,
            Application.scholarship_id == payload.scholarship_id,
        )
    ).scalar_one_or_none()

    if row is None:
        row = Application(
            user_id=user.id,
            scholarship_id=payload.scholarship_id,
            status=payload.status,
            notes=payload.notes,
            applied_on=payload.applied_on
            or (date.today() if payload.status == "applied" else None),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Two Apply clicks raced; fall through to the existing row.
            db.rollback()
            row = db.execute(
                select(Application).where(
                    Application.user_id == user.id,
                    Application.scholarship_id == payload.scholarship_id,
                )
            ).scalar_one()
    else:
        # Never downgrade real progress back to "saved" just because the user
        # clicked Apply again on an entry they had already moved forward.
        if not (payload.status == "saved" and row.status != "saved"):
            row.status = payload.status
        if payload.notes is not None:
            row.notes = payload.notes
        if payload.applied_on is not None:
            row.applied_on = payload.applied_on
        elif row.status == "applied" and row.applied_on is None:
            row.applied_on = date.today()
        db.commit()

    db.refresh(row)
    return _to_out(row)


@router.patch("/{application_id}", response_model=ApplicationOut)
def patch_application(
    application_id: int,
    payload: ApplicationPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationOut:
    row = _owned(db, user, application_id)

    fields = payload.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] is not None:
        row.status = fields["status"]
        # Stamp the date the first time it reaches "applied".
        if row.status == "applied" and row.applied_on is None:
            row.applied_on = date.today()
    if "notes" in fields:
        row.notes = fields["notes"]
    if "applied_on" in fields:
        row.applied_on = fields["applied_on"]

    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    row = _owned(db, user, application_id)
    db.delete(row)
    db.commit()
