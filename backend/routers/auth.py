"""Signup, login, and the current-user endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    is_admin,
    verify_password,
)
from backend.db import get_db
from backend.models import User
from backend.schemas import LoginIn, SignupIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        is_admin=is_admin(user),
    )


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupIn, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower()

    existing = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email, name=payload.name, password_hash=hash_password(payload.password)
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent signup with the same email.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    db.refresh(user)

    return TokenOut(access_token=create_access_token(user), user=_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower())
    ).scalar_one_or_none()

    # Same message either way so the endpoint does not reveal which emails exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    return TokenOut(access_token=create_access_token(user), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
