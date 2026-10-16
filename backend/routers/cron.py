"""Scheduled and manual refresh endpoints.

Vercel Cron calls GET /api/cron/refresh with `Authorization: Bearer $CRON_SECRET`
and anything else must be rejected (spec §4). The admin variant is for the
manual refresh button in the UI.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import require_admin
from backend.config import settings
from backend.db import get_db
from backend.models import User
from backend.schemas import RefreshOut
from backend.services.ingest import run_ingest

log = logging.getLogger(__name__)

router = APIRouter(tags=["refresh"])


def _to_out(run) -> RefreshOut:
    return RefreshOut(
        ok=run.ok,
        trigger=run.trigger,
        started_at=run.started_at,
        finished_at=run.finished_at,
        summary=run.summary or {},
    )


def _verify_cron_secret(authorization: str | None) -> None:
    if not settings.cron_secret:
        # Refuse rather than run unauthenticated if the secret was never set.
        log.error("CRON_SECRET is not configured; refusing the refresh request")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh is not configured",
        )

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )

    # Constant-time comparison so the secret cannot be guessed byte by byte.
    if not hmac.compare_digest(token.strip(), settings.cron_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret"
        )


@router.get("/cron/refresh", response_model=RefreshOut)
def cron_refresh(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> RefreshOut:
    _verify_cron_secret(authorization)
    return _to_out(run_ingest(db, trigger="cron"))


@router.post("/admin/refresh", response_model=RefreshOut)
def admin_refresh(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> RefreshOut:
    log.info("manual refresh triggered by %s", user.email)
    return _to_out(run_ingest(db, trigger=f"manual:{user.email}"))
