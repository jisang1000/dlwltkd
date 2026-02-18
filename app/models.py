from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    consultation_card: Mapped[ConsultationCard | None] = relationship(
        back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )
    reservations: Mapped[list[Reservation]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="reservations")
    treatment_record: Mapped[TreatmentRecord | None] = relationship(
        back_populates="reservation", uselist=False, cascade="all, delete-orphan"
    )


class ConsultationCard(Base):
    __tablename__ = "consultation_cards"
    __table_args__ = (UniqueConstraint("customer_id", name="uq_consultation_cards_customer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    skin_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    contraindications: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="consultation_card")


class TreatmentRecord(Base):
    __tablename__ = "treatment_records"
    __table_args__ = (UniqueConstraint("reservation_id", name="uq_treatment_records_reservation_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    treatment_summary: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    reservation: Mapped[Reservation] = relationship(back_populates="treatment_record")
    product_usages: Mapped[list[ProductUsage]] = relationship(
        back_populates="treatment_record", cascade="all, delete-orphan"
    )


class ProductUsage(Base):
    __tablename__ = "product_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    treatment_record_id: Mapped[int] = mapped_column(
        ForeignKey("treatment_records.id", ondelete="CASCADE"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    treatment_record: Mapped[TreatmentRecord] = relationship(back_populates="product_usages")
