import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .providers import GREENHOUSE_BOARDS, LEVER_SITES, search_public_company_boards
from .verification import verify_job_listing

app = FastAPI(title="Nova Career Intelligence API", version="0.3.0")
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
    allow_methods=["GET", "POST"],
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

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Keep the production pilot scoped to the US until India sources and
        # location matching are implemented and tested as a separate phase.
        if isinstance(obj, dict) and obj.get("location", "United States").strip().lower() not in {"united states", "usa", "us"}:
            raise ValueError("Only United States job search is enabled in this phase.")
        return super().model_validate(obj, *args, **kwargs)


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
