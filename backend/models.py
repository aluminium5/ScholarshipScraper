"""SQLAlchemy models (spec §5).

JSON columns are used for the portfolio sections: the shapes are form-driven and
change often, and nothing queries inside them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    portfolio: Mapped["Portfolio | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Scholarship(Base):
    __tablename__ = "scholarships"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_scholarship_source_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    award_amount: Mapped[str | None] = mapped_column(String(300))
    eligibility: Mapped[str | None] = mapped_column(Text)

    level: Mapped[str] = mapped_column(String(16), default="any", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    opens_at: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date, index=True)

    # The deep link (spec §6). Never a portal homepage.
    apply_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    info_url: Mapped[str | None] = mapped_column(String(1000))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="scholarship", cascade="all, delete-orphan"
    )


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )

    # Free-form sections. See schemas.py for the validated shape; bank holds only
    # the last 4 digits and documents hold no identity numbers at all (spec §5).
    personal: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    academic: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    family: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    bank: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    documents: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    cv: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="portfolio")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "scholarship_id", name="uq_application_user_scholarship"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scholarship_id: Mapped[int] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(String(24), default="saved", nullable=False)
    applied_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="applications")
    scholarship: Mapped[Scholarship] = relationship(back_populates="applications")


class RefreshRun(Base):
    """One row per ingest run so the UI can show "Updated 3h ago" (spec §7.5.6)."""

    __tablename__ = "refresh_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trigger: Mapped[str] = mapped_column(String(24), default="cron", nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
