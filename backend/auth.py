"""Password hashing, JWT issue/verify, and the current-user dependency."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import get_db
from backend.models import User

# auto_error=False so we can raise a consistent 401 shape ourselves.
_bearer = HTTPBearer(auto_error=False)

# bcrypt truncates at 72 bytes and errors on longer input in 4.x.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        pw = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/legacy hash in the row: treat as a failed login, not a 500.
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise _unauthorized()
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid token") from None

    subject = payload.get("sub")
    if not subject:
        raise _unauthorized("Invalid token")

    user = db.execute(select(User).where(User.id == int(subject))).scalar_one_or_none()
    if user is None:
        raise _unauthorized("User no longer exists")
    return user


def is_admin(user: User) -> bool:
    return user.email.lower() in settings.admin_emails


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
