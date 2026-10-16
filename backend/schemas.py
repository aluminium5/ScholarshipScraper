"""Pydantic v2 request/response schemas."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

LEVELS = ("school", "ug", "pg", "phd", "any")
STATUSES = ("saved", "applied", "under_review", "awarded", "rejected")

Level = Literal["school", "ug", "pg", "phd", "any"]
AppStatus = Literal["saved", "applied", "under_review", "awarded", "rejected"]


# --------------------------------------------------------------------------- auth
class SignupIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=160)]
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    created_at: datetime
    is_admin: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# -------------------------------------------------------------------- scholarships
class ScholarshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    title: str
    provider: str | None = None
    description: str | None = None
    award_amount: str | None = None
    eligibility: str | None = None
    level: str
    tags: list[str] = Field(default_factory=list)
    opens_at: date | None = None
    deadline: date | None = None
    apply_url: str
    info_url: str | None = None
    is_active: bool
    last_seen_at: datetime | None = None

    # Computed per request / joined from the caller's applications.
    days_left: int | None = None
    application_status: AppStatus | None = None
    application_id: int | None = None


class ScholarshipListOut(BaseModel):
    items: list[ScholarshipOut]
    total: int


class SourceCount(BaseModel):
    source: str
    count: int


class ScholarshipMetaOut(BaseModel):
    sources: list[SourceCount]
    levels: list[SourceCount]
    tags: list[SourceCount]
    total_active: int
    closing_this_week: int
    expired_hidden: int
    last_refresh_at: datetime | None = None
    last_refresh_summary: dict[str, Any] = Field(default_factory=dict)


# ----------------------------------------------------------------------- portfolio
class DocumentItem(BaseModel):
    """One row of the documents checklist. Deliberately holds no ID numbers."""

    have: bool = False
    expires_on: date | None = None
    note: str | None = Field(default=None, max_length=300)


class PersonalSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=160)
    dob: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=24)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    state: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=32)
    religion: str | None = Field(default=None, max_length=48)
    disability_status: str | None = Field(default=None, max_length=120)


class AcademicSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_course: str | None = Field(default=None, max_length=160)
    institution: str | None = Field(default=None, max_length=200)
    year_or_semester: str | None = Field(default=None, max_length=48)
    cgpa_or_percentage: str | None = Field(default=None, max_length=32)
    class_10_percentage: str | None = Field(default=None, max_length=32)
    class_12_percentage: str | None = Field(default=None, max_length=32)
    roll_or_enrollment_no: str | None = Field(default=None, max_length=64)


class FamilySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    father_name: str | None = Field(default=None, max_length=160)
    father_occupation: str | None = Field(default=None, max_length=160)
    mother_name: str | None = Field(default=None, max_length=160)
    mother_occupation: str | None = Field(default=None, max_length=160)
    annual_family_income: str | None = Field(default=None, max_length=48)


class BankSection(BaseModel):
    """Only the last 4 digits are ever accepted or stored (spec sections 5 and 11)."""

    model_config = ConfigDict(extra="forbid")

    account_holder_name: str | None = Field(default=None, max_length=160)
    bank_name: str | None = Field(default=None, max_length=160)
    ifsc: str | None = Field(default=None, max_length=16)
    account_last4: str | None = Field(default=None, max_length=4)

    @field_validator("account_last4")
    @classmethod
    def _only_last4(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        digits = re.sub(r"\D", "", v)
        if len(digits) != 4:
            raise ValueError("Store the last 4 digits only")
        return digits

    @field_validator("ifsc")
    @classmethod
    def _upper_ifsc(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v


class CvSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = Field(default=None, max_length=2000)
    skills: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    extracurriculars: list[str] = Field(default_factory=list)
    github: str | None = Field(default=None, max_length=300)
    linkedin: str | None = Field(default=None, max_length=300)
    other_links: list[str] = Field(default_factory=list)


DOCUMENT_KEYS = (
    "aadhaar",
    "income_certificate",
    "caste_certificate",
    "domicile",
    "marksheets",
    "fee_receipt",
    "bonafide",
    "bank_passbook",
    "photo",
)


class PortfolioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personal: PersonalSection = Field(default_factory=PersonalSection)
    academic: AcademicSection = Field(default_factory=AcademicSection)
    family: FamilySection = Field(default_factory=FamilySection)
    bank: BankSection = Field(default_factory=BankSection)
    documents: dict[str, DocumentItem] = Field(default_factory=dict)
    cv: CvSection = Field(default_factory=CvSection)

    @field_validator("documents")
    @classmethod
    def _known_documents(cls, v: dict[str, DocumentItem]) -> dict[str, DocumentItem]:
        unknown = set(v) - set(DOCUMENT_KEYS)
        if unknown:
            raise ValueError("Unknown document keys: " + ", ".join(sorted(unknown)))
        return v


class PortfolioOut(PortfolioIn):
    updated_at: datetime | None = None


# -------------------------------------------------------------------- applications
class ApplicationIn(BaseModel):
    scholarship_id: int
    status: AppStatus = "saved"
    notes: str | None = Field(default=None, max_length=2000)
    applied_on: date | None = None


class ApplicationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AppStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    applied_on: date | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scholarship_id: int
    status: AppStatus
    applied_on: date | None = None
    notes: str | None = None
    updated_at: datetime
    scholarship: ScholarshipOut | None = None


# ------------------------------------------------------------------------- refresh
class RefreshOut(BaseModel):
    ok: bool
    trigger: str
    started_at: datetime
    finished_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
