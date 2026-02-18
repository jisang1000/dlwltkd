from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import AppointmentStatus


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    hair_concern: str | None = Field(default=None, max_length=255)


class CustomerRead(CustomerCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StylistCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    specialty: str = Field(min_length=2, max_length=120)


class StylistRead(StylistCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    duration_min: int = Field(gt=0, le=600)
    price: float = Field(gt=0, le=1_000_000)


class ServiceRead(ServiceCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    customer_id: int = Field(gt=0)
    stylist_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    starts_at: datetime
    notes: str | None = Field(default=None, max_length=255)


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class AppointmentRead(BaseModel):
    id: int
    customer_id: int
    stylist_id: int
    service_id: int
    starts_at: datetime
    status: AppointmentStatus
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    today_total_appointments: int
    today_completed_appointments: int
    today_cancellation_rate: float
    today_estimated_revenue: float
