"""Request/response shapes for creating and editing loans."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import Platform

Money = Decimal  # million toman, up to 3 decimals


class JalaliDate(BaseModel):
    year: int = Field(ge=1300, le=1500)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)


class ScheduledInstallment(JalaliDate):
    amount: Money = Field(gt=0, max_digits=18, decimal_places=3)


class LenderShare(BaseModel):
    person_id: int
    amount: Money = Field(gt=0, max_digits=18, decimal_places=3)


class SchedulePreviewRequest(BaseModel):
    lenders: list[LenderShare] = Field(min_length=1, max_length=200)
    months: int = Field(ge=1, le=60)
    first_due: JalaliDate


class LenderSchedule(BaseModel):
    person_id: int
    amount: Money
    installments: list[ScheduledInstallment]


class SchedulePreview(BaseModel):
    lenders: list[LenderSchedule]


class LoanCreate(BaseModel):
    borrower_id: int
    topic_id: int
    lenders: list[LenderSchedule] = Field(min_length=1, max_length=200)
    persian_year: int | None = Field(default=None, ge=1300, le=1500)
    issued: JalaliDate | None = None
    guarantor_id: int | None = None
    liaison_person_id: int | None = None
    liaison_label: str | None = Field(default=None, max_length=80)
    source_platform: Platform | None = None
    description: str | None = Field(default=None, max_length=4000)
    note_flagged: bool = False


class LoanUpdate(BaseModel):
    """PATCH body; omitted fields stay unchanged, explicit null clears."""

    topic_id: int | None = None
    guarantor_id: int | None = None
    liaison_person_id: int | None = None
    source_platform: Platform | None = None
    description: str | None = Field(default=None, max_length=4000)
    note_flagged: bool | None = None
    issued: JalaliDate | None = None


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)


class CreatedResponse(BaseModel):
    id: int
