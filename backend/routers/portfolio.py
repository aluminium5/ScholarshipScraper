"""The student's reusable portfolio: read and whole-document replace."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.db import get_db
from backend.models import Portfolio, User
from backend.schemas import PortfolioIn, PortfolioOut

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _get_or_create(db: Session, user: User) -> Portfolio:
    row = db.execute(
        select(Portfolio).where(Portfolio.user_id == user.id)
    ).scalar_one_or_none()
    if row is not None:
        return row

    row = Portfolio(
        user_id=user.id,
        personal={},
        academic={},
        family={},
        bank={},
        documents={},
        cv={},
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent first-write for the same user; re-read the winner.
        db.rollback()
        row = db.execute(
            select(Portfolio).where(Portfolio.user_id == user.id)
        ).scalar_one()
        return row
    db.refresh(row)
    return row


def _to_out(row: Portfolio) -> PortfolioOut:
    return PortfolioOut(
        personal=row.personal or {},
        academic=row.academic or {},
        family=row.family or {},
        bank=row.bank or {},
        documents=row.documents or {},
        cv=row.cv or {},
        updated_at=row.updated_at,
    )


@router.get("", response_model=PortfolioOut)
def get_portfolio(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> PortfolioOut:
    return _to_out(_get_or_create(db, user))


@router.put("", response_model=PortfolioOut)
def replace_portfolio(
    payload: PortfolioIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PortfolioOut:
    row = _get_or_create(db, user)

    # mode="json" so dates land in the JSON column as ISO strings.
    row.personal = payload.personal.model_dump(mode="json")
    row.academic = payload.academic.model_dump(mode="json")
    row.family = payload.family.model_dump(mode="json")
    # BankSection's validator has already reduced the account to 4 digits.
    row.bank = payload.bank.model_dump(mode="json")
    row.documents = {k: v.model_dump(mode="json") for k, v in payload.documents.items()}
    row.cv = payload.cv.model_dump(mode="json")

    db.commit()
    db.refresh(row)
    return _to_out(row)
