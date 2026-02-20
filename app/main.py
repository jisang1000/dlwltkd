from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, schemas
from .ai.routes import router as ai_router
from .database import Base, engine, get_db

app = FastAPI(title="HairInfo 헤어샵 관리 API", version="0.2.0")

Base.metadata.create_all(bind=engine)

app.include_router(ai_router)

UI_DIR = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


@app.get("/", include_in_schema=False)
def ui_index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.post("/customers", response_model=schemas.CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)) -> schemas.CustomerRead:
    try:
        return crud.create_customer(db, payload)
    except crud.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/stylists", response_model=schemas.StylistRead, status_code=status.HTTP_201_CREATED)
def create_stylist(payload: schemas.StylistCreate, db: Session = Depends(get_db)) -> schemas.StylistRead:
    return crud.create_stylist(db, payload)


@app.post("/services", response_model=schemas.ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(payload: schemas.ServiceCreate, db: Session = Depends(get_db)) -> schemas.ServiceRead:
    try:
        return crud.create_service(db, payload)
    except crud.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/appointments", response_model=schemas.AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db)) -> schemas.AppointmentRead:
    try:
        return crud.create_appointment(db, payload)
    except crud.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except crud.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/appointments", response_model=list[schemas.AppointmentRead])
def list_appointments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[schemas.AppointmentRead]:
    return crud.list_appointments(db, limit=limit, offset=offset)


@app.patch("/appointments/{appointment_id}/status", response_model=schemas.AppointmentRead)
def update_appointment_status(
    appointment_id: int,
    payload: schemas.AppointmentStatusUpdate,
    db: Session = Depends(get_db),
) -> schemas.AppointmentRead:
    try:
        return crud.update_appointment_status(db, appointment_id=appointment_id, status=payload.status)
    except crud.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.get("/dashboard/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> schemas.DashboardSummary:
    return crud.get_dashboard_summary(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
