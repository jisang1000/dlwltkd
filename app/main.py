from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import Base, engine, get_db
from app.models import ConsultationCard, Customer, ProductUsage, Reservation, TreatmentRecord
from app.schemas import (
    ConsultationCardCreate,
    ConsultationCardRead,
    ConsultationCardUpdate,
    CustomerCreate,
    CustomerRead,
    ReservationCompleteWithRecordRequest,
    ReservationCreate,
    ReservationRead,
    RevisitRecommendationRead,
    TreatmentRecordRead,
    mask_phone,
    mask_sensitive_text,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clinic CRM API", version="0.1.0")


@app.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> CustomerRead:
    existing = db.scalar(select(Customer).where(Customer.phone == payload.phone))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already exists")

    customer = Customer(name=payload.name.strip(), phone=payload.phone.strip())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerRead(
        id=customer.id,
        name=customer.name,
        phone_masked=mask_phone(customer.phone),
        created_at=customer.created_at,
    )


@app.post("/reservations", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_reservation(payload: ReservationCreate, db: Session = Depends(get_db)) -> Reservation:
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    reservation = Reservation(**payload.model_dump(), status="scheduled")
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


@app.post("/consultation-cards", response_model=ConsultationCardRead, status_code=status.HTTP_201_CREATED)
def create_consultation_card(payload: ConsultationCardCreate, db: Session = Depends(get_db)) -> ConsultationCardRead:
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    if customer.consultation_card:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Consultation card already exists")

    card = ConsultationCard(**payload.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return to_consultation_card_read(card)


@app.get("/consultation-cards/{customer_id}", response_model=ConsultationCardRead)
def get_consultation_card(customer_id: int, db: Session = Depends(get_db)) -> ConsultationCardRead:
    card = db.scalar(select(ConsultationCard).where(ConsultationCard.customer_id == customer_id))
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation card not found")
    return to_consultation_card_read(card)


@app.put("/consultation-cards/{customer_id}", response_model=ConsultationCardRead)
def update_consultation_card(
    customer_id: int, payload: ConsultationCardUpdate, db: Session = Depends(get_db)
) -> ConsultationCardRead:
    card = db.scalar(select(ConsultationCard).where(ConsultationCard.customer_id == customer_id))
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation card not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field_name, value)

    db.commit()
    db.refresh(card)
    return to_consultation_card_read(card)


@app.delete("/consultation-cards/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consultation_card(customer_id: int, db: Session = Depends(get_db)) -> None:
    card = db.scalar(select(ConsultationCard).where(ConsultationCard.customer_id == customer_id))
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation card not found")
    db.delete(card)
    db.commit()


@app.post(
    "/reservations/{reservation_id}/complete",
    response_model=TreatmentRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def complete_reservation_with_treatment_record(
    reservation_id: int,
    payload: ReservationCompleteWithRecordRequest,
    db: Session = Depends(get_db),
) -> TreatmentRecordRead:
    reservation = db.scalar(
        select(Reservation)
        .options(joinedload(Reservation.treatment_record))
        .where(Reservation.id == reservation_id)
    )
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if reservation.treatment_record:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Treatment record already exists")

    treatment_payload = payload.treatment_record
    record = TreatmentRecord(
        reservation_id=reservation_id,
        provider_name=treatment_payload.provider_name,
        treatment_summary=treatment_payload.treatment_summary,
        follow_up_notes=treatment_payload.follow_up_notes,
        completed_at=treatment_payload.completed_at,
    )
    record.product_usages = [ProductUsage(**usage.model_dump()) for usage in treatment_payload.product_usages]
    reservation.status = "completed"
    db.add(record)
    db.commit()
    db.refresh(record)
    return to_treatment_record_read(record)


@app.get("/dashboard/revisit-recommendations", response_model=list[RevisitRecommendationRead])
def get_revisit_recommendations(
    inactivity_days: int = Query(default=60, ge=30, le=365),
    high_value_threshold: float = Query(default=200_000, gt=0),
    min_high_value_visits: int = Query(default=1, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[RevisitRecommendationRead]:
    if inactivity_days % 5 != 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="inactivity_days must be multiple of 5")

    cutoff = datetime.utcnow() - timedelta(days=inactivity_days)

    high_value_count = func.sum(
        case((Reservation.total_price >= high_value_threshold, 1), else_=0)
    ).label("high_value_visit_count")

    query = (
        select(
            Customer.id.label("customer_id"),
            Customer.name.label("customer_name"),
            Customer.phone.label("phone"),
            func.max(TreatmentRecord.completed_at).label("last_visit_at"),
            high_value_count,
        )
        .join(Reservation, Reservation.customer_id == Customer.id)
        .join(TreatmentRecord, TreatmentRecord.reservation_id == Reservation.id)
        .where(and_(Reservation.status == "completed"))
        .group_by(Customer.id)
        .having(
            and_(
                func.max(TreatmentRecord.completed_at) < cutoff,
                high_value_count >= min_high_value_visits,
            )
        )
        .order_by(func.max(TreatmentRecord.completed_at).asc())
    )

    rows = db.execute(query).all()
    result: list[RevisitRecommendationRead] = []
    now = datetime.utcnow()
    for row in rows:
        last_visit_at = row.last_visit_at
        result.append(
            RevisitRecommendationRead(
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                phone_masked=mask_phone(row.phone),
                last_visit_at=last_visit_at,
                days_since_last_visit=(now - last_visit_at).days,
                high_value_visit_count=int(row.high_value_visit_count or 0),
            )
        )
    return result


def to_consultation_card_read(card: ConsultationCard) -> ConsultationCardRead:
    return ConsultationCardRead(
        id=card.id,
        customer_id=card.customer_id,
        skin_type=card.skin_type,
        allergies_masked=mask_sensitive_text(card.allergies),
        contraindications_masked=mask_sensitive_text(card.contraindications),
        notes_masked=mask_sensitive_text(card.notes),
        consent_at=card.consent_at,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def to_treatment_record_read(record: TreatmentRecord) -> TreatmentRecordRead:
    return TreatmentRecordRead(
        id=record.id,
        reservation_id=record.reservation_id,
        provider_name=record.provider_name,
        treatment_summary_masked=mask_sensitive_text(record.treatment_summary) or "",
        follow_up_notes_masked=mask_sensitive_text(record.follow_up_notes),
        completed_at=record.completed_at,
        product_usages=record.product_usages,
    )
