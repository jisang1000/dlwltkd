from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Appointment, AppointmentStatus, Customer, Service, Stylist
from .schemas import (
    AppointmentCreate,
    CustomerCreate,
    DashboardSummary,
    ServiceCreate,
    StylistCreate,
)


class NotFoundError(ValueError):
    pass


class ConflictError(ValueError):
    pass


def create_customer(db: Session, payload: CustomerCreate) -> Customer:
    exists = db.scalar(select(Customer).where(Customer.phone == payload.phone))
    if exists:
        raise ConflictError("이미 등록된 전화번호입니다.")

    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def create_stylist(db: Session, payload: StylistCreate) -> Stylist:
    stylist = Stylist(**payload.model_dump())
    db.add(stylist)
    db.commit()
    db.refresh(stylist)
    return stylist


def create_service(db: Session, payload: ServiceCreate) -> Service:
    exists = db.scalar(select(Service).where(Service.name == payload.name))
    if exists:
        raise ConflictError("동일한 서비스명이 이미 존재합니다.")

    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def _validate_references(db: Session, payload: AppointmentCreate) -> None:
    customer = db.scalar(select(Customer.id).where(Customer.id == payload.customer_id))
    stylist = db.scalar(select(Stylist.id).where(Stylist.id == payload.stylist_id))
    service = db.scalar(select(Service.id).where(Service.id == payload.service_id))

    if not customer:
        raise NotFoundError("고객 정보를 찾을 수 없습니다.")
    if not stylist:
        raise NotFoundError("디자이너 정보를 찾을 수 없습니다.")
    if not service:
        raise NotFoundError("서비스 정보를 찾을 수 없습니다.")


def create_appointment(db: Session, payload: AppointmentCreate) -> Appointment:
    _validate_references(db, payload)

    overlapping = db.scalar(
        select(Appointment).where(
            Appointment.stylist_id == payload.stylist_id,
            Appointment.starts_at == payload.starts_at,
            Appointment.status == AppointmentStatus.SCHEDULED,
        )
    )
    if overlapping:
        raise ConflictError("해당 디자이너의 같은 시간 예약이 이미 존재합니다.")

    appointment = Appointment(**payload.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def list_appointments(db: Session, limit: int = 100, offset: int = 0) -> list[Appointment]:
    stmt = (
        select(Appointment)
        .order_by(Appointment.starts_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def update_appointment_status(db: Session, appointment_id: int, status: AppointmentStatus) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("예약을 찾을 수 없습니다.")

    appointment.status = status
    db.commit()
    db.refresh(appointment)
    return appointment


def get_dashboard_summary(db: Session, target: datetime | None = None) -> DashboardSummary:
    now = target or datetime.now()
    start = datetime.combine(now.date(), time.min)
    end = datetime.combine(now.date(), time.max)

    total = db.scalar(
        select(func.count(Appointment.id)).where(Appointment.starts_at >= start, Appointment.starts_at <= end)
    ) or 0

    completed = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.starts_at >= start,
            Appointment.starts_at <= end,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    ) or 0

    cancelled = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.starts_at >= start,
            Appointment.starts_at <= end,
            Appointment.status == AppointmentStatus.CANCELLED,
        )
    ) or 0

    revenue = db.scalar(
        select(func.coalesce(func.sum(Service.price), 0.0))
        .select_from(Appointment)
        .join(Service, Service.id == Appointment.service_id)
        .where(
            Appointment.starts_at >= start,
            Appointment.starts_at <= end,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    ) or 0.0

    cancellation_rate = float(cancelled / total) if total else 0.0

    return DashboardSummary(
        today_total_appointments=total,
        today_completed_appointments=completed,
        today_cancellation_rate=round(cancellation_rate, 4),
        today_estimated_revenue=float(revenue),
    )
