from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=8, max_length=20)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str
    created_at: datetime


class ReservationCreate(BaseModel):
    customer_id: int
    service_name: str = Field(min_length=1, max_length=120)
    total_price: float = Field(gt=0)
    reserved_at: datetime


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    service_name: str
    total_price: float
    reserved_at: datetime
    status: str


class ConsultationCardCreate(BaseModel):
    customer_id: int
    skin_type: str | None = Field(default=None, max_length=50)
    allergies: str | None = None
    contraindications: str | None = None
    notes: str | None = None
    consent_at: date | None = None


class ConsultationCardUpdate(BaseModel):
    skin_type: str | None = Field(default=None, max_length=50)
    allergies: str | None = None
    contraindications: str | None = None
    notes: str | None = None
    consent_at: date | None = None


class ConsultationCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    skin_type: str | None
    allergies_masked: str | None
    contraindications_masked: str | None
    notes_masked: str | None
    consent_at: date | None
    created_at: datetime
    updated_at: datetime


class ProductUsageCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=150)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    notes: str | None = None


class ProductUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_name: str
    quantity: float
    unit: str
    notes: str | None


class TreatmentRecordCreate(BaseModel):
    provider_name: str = Field(min_length=1, max_length=100)
    treatment_summary: str = Field(min_length=1)
    follow_up_notes: str | None = None
    completed_at: datetime
    product_usages: list[ProductUsageCreate] = Field(default_factory=list)


class TreatmentRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    provider_name: str
    treatment_summary_masked: str
    follow_up_notes_masked: str | None
    completed_at: datetime
    product_usages: list[ProductUsageRead]


class ReservationCompleteWithRecordRequest(BaseModel):
    treatment_record: TreatmentRecordCreate


class RevisitRecommendationRead(BaseModel):
    customer_id: int
    customer_name: str
    phone_masked: str
    last_visit_at: datetime
    days_since_last_visit: int
    high_value_visit_count: int


class DashboardRecommendationQuery(BaseModel):
    inactivity_days: int = Field(default=60, ge=30, le=365)
    high_value_threshold: float = Field(default=200_000, gt=0)
    min_high_value_visits: int = Field(default=1, ge=1, le=100)

    @field_validator("inactivity_days")
    @classmethod
    def ensure_practical_window(cls, value: int) -> int:
        if value % 5 != 0:
            raise ValueError("inactivity_days must be a multiple of 5 for dashboard bucketing")
        return value


def mask_phone(phone: str) -> str:
    if len(phone) <= 4:
        return "*" * len(phone)
    prefix = phone[:3]
    suffix = phone[-2:]
    return f"{prefix}{'*' * max(0, len(phone) - 5)}{suffix}"


def mask_sensitive_text(value: str | None, exposed: int = 2) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    if not compact:
        return compact
    if len(compact) <= exposed:
        return "*" * len(compact)
    return f"{compact[:exposed]}{'*' * (len(compact) - exposed)}"
