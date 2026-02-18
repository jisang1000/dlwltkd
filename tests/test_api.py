from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_hairinfo.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)



def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)



def test_end_to_end_flow() -> None:
    customer = client.post(
        "/customers",
        json={"name": "김고객", "phone": "01012341234", "hair_concern": "손상모"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    stylist = client.post("/stylists", json={"name": "박디자이너", "specialty": "레이어드컷"})
    assert stylist.status_code == 201
    stylist_id = stylist.json()["id"]

    service = client.post("/services", json={"name": "펌", "duration_min": 120, "price": 150000})
    assert service.status_code == 201
    service_id = service.json()["id"]

    starts_at = (datetime.now() + timedelta(hours=1)).isoformat()
    appointment = client.post(
        "/appointments",
        json={
            "customer_id": customer_id,
            "stylist_id": stylist_id,
            "service_id": service_id,
            "starts_at": starts_at,
            "notes": "두피 민감",
        },
    )
    assert appointment.status_code == 201
    appointment_id = appointment.json()["id"]

    updated = client.patch(f"/appointments/{appointment_id}/status", json={"status": "completed"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"

    summary = client.get("/dashboard/summary")
    assert summary.status_code == 200
    assert summary.json()["today_total_appointments"] == 1
    assert summary.json()["today_completed_appointments"] == 1
    assert summary.json()["today_estimated_revenue"] == 150000.0



def test_conflict_duplicate_phone() -> None:
    payload = {"name": "김고객", "phone": "01012341234", "hair_concern": "곱슬"}
    assert client.post("/customers", json=payload).status_code == 201
    conflict = client.post("/customers", json=payload)
    assert conflict.status_code == 409
