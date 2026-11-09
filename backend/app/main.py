import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, String, Integer, Date, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import date, datetime

from .providers import GREENHOUSE_BOARDS, LEVER_SITES, search_public_company_boards
from .verification import verify_job_listing

app = FastAPI(title="Nova Career Intelligence API", version="0.4.0")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nova.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workspace_id: Mapped[str] = mapped_column(String(80), index=True)
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="Applied")
    platform: Mapped[str] = mapped_column(String(100), default="Manual")
    job_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    interview_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

Base.metadata.create_all(bind=engine)

class ApplicationInput(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=300)
    status: str = Field(default="Applied", max_length=30)
    platform: str = Field(default="Manual", max_length=100)
    job_url: str | None = Field(default=None, max_length=2000)
    applied_date: date | None = None
    follow_up_date: date | None = None
    interview_date: date | None = None
    notes: str = Field(default="", max_length=5000)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value not in {"Applied", "Pending", "Responded", "Interview", "Rejected", "Offer", "Withdrawn"}:
            raise ValueError("Unsupported application status.")
        return value

class ApplicationUpdate(ApplicationInput):
    pass

def serialize_application(item):
    return {"id": item.id, "company": item.company, "role": item.role, "status": item.status,
            "platform": item.platform, "job_url": item.job_url,
            "applied_date": item.applied_date.isoformat() if item.applied_date else None,
            "follow_up_date": item.follow_up_date.isoformat() if item.follow_up_date else None,
            "interview_date": item.interview_date.isoformat() if item.interview_date else None,
            "notes": item.notes, "created_at": item.created_at.isoformat() if item.created_at else None}

def valid_workspace(workspace_id: str):
    if not workspace_id or len(workspace_id) > 80 or len(workspace_id) < 20:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="A valid workspace ID is required.")
    return workspace_id
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

allowed_origins = [
    origin.strip()
    for origin in os.getenv("NOVA_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

PLATFORMS = [
    {"id": "linkedin", "name": "LinkedIn", "search": "Not connected", "application": "Manual"},
    {"id": "indeed", "name": "Indeed", "search": "Not connected", "application": "Manual"},
    {"id": "glassdoor", "name": "Glassdoor", "search": "Not connected", "application": "Manual"},
    {"id": "ziprecruiter", "name": "ZipRecruiter", "search": "Not connected", "application": "Manual"},
    {"id": "dice", "name": "Dice", "search": "Not connected", "application": "Manual"},
    {"id": "wellfound", "name": "Wellfound", "search": "Not connected", "application": "Manual"},
    {"id": "career", "name": "Company career pages", "search": "Greenhouse / Lever when configured", "application": "Manual"},
    {"id": "other", "name": "Other supported portals", "search": "Not connected", "application": "Manual"},
]


class JobSearchRequest(BaseModel):
    query: str = Field(default="", max_length=300)
    location: str = Field(default="United States", max_length=120)
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("location")
    @classmethod
    def only_us_market_in_this_phase(cls, value: str) -> str:
        if value.strip().lower() not in {"united states", "usa", "us"}:
            raise ValueError("Only United States job search is enabled in this phase.")
        return "United States"


class JobVerificationRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=8, max_length=2000)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=200)


@app.get("/")
def root():
    if FRONTEND_DIST.joinpath("index.html").is_file():
        return FileResponse(FRONTEND_DIST / "index.html")
    return {"name": "Nova Career Intelligence", "status": "api-ready", "version": "0.3.0"}


@app.get("/api/v1/applications")
def list_applications(workspace_id: str):
    with SessionLocal() as db:
        rows = db.query(Application).filter(Application.workspace_id == valid_workspace(workspace_id)).order_by(Application.applied_date.desc(), Application.id.desc()).all()
        return {"applications": [serialize_application(row) for row in rows]}

@app.post("/api/v1/applications")
def create_application(payload: ApplicationInput, workspace_id: str):
    with SessionLocal() as db:
        row = Application(workspace_id=valid_workspace(workspace_id), **payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return serialize_application(row)

@app.put("/api/v1/applications/{application_id}")
def update_application(application_id: int, payload: ApplicationUpdate, workspace_id: str):
    with SessionLocal() as db:
        row = db.query(Application).filter(Application.id == application_id, Application.workspace_id == valid_workspace(workspace_id)).first()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Application not found.")
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        db.commit()
        db.refresh(row)
        return serialize_application(row)

@app.delete("/api/v1/applications/{application_id}")
def delete_application(application_id: int, workspace_id: str):
    with SessionLocal() as db:
        row = db.query(Application).filter(Application.id == application_id, Application.workspace_id == valid_workspace(workspace_id)).first()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Application not found.")
        db.delete(row)
        db.commit()
        return {"deleted": True}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/platforms")
def get_platforms():
    return {"platforms": PLATFORMS}


@app.get("/api/v1/config")
def get_config():
    configured_boards = len(GREENHOUSE_BOARDS) + len(LEVER_SITES)
    return {
        "resume_upload_enabled": False,
        "application_tracking_enabled": True,
        "application_storage": "database",
        "live_job_search_enabled": configured_boards > 0,
        "job_verification_enabled": True,
        "pilot_application_enabled": True,
        "application_submission_enabled": False,
        "provider_integrations_configured": configured_boards > 0,
        "configured_public_boards": configured_boards,
        "message": "Nova can search configured public Greenhouse and Lever boards and verify exact live listings. The pilot guides the user to the employer application page; automated submission and server-side resume storage are disabled."
    }


@app.post("/api/v1/search")
async def search_jobs(request: JobSearchRequest):
    return await search_public_company_boards(
        query=request.query,
        location=request.location,
        limit=request.limit,
    )


@app.post('/api/v1/verify-job')
async def verify_job(request: JobVerificationRequest):
    return await verify_job_listing(
        job_id=request.job_id,
        submitted_url=request.url,
        submitted_title=request.title,
        submitted_company=request.company,
    )


if FRONTEND_DIST.exists():
    app.mount('/assets', StaticFiles(directory=str(FRONTEND_DIST / 'assets')), name='frontend-assets')

    @app.get('/{full_path:path}')
    def frontend_fallback(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / 'index.html')
