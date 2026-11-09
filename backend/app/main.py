import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .providers import GREENHOUSE_BOARDS, LEVER_SITES, search_public_company_boards

app = FastAPI(title="Nova Career Intelligence API", version="0.2.0")

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


@app.get("/")
def root():
    return {"name": "Nova Career Intelligence API", "status": "preview", "version": "0.2.0"}


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
        "application_submission_enabled": False,
        "provider_integrations_configured": configured_boards > 0,
        "configured_public_boards": configured_boards,
        "message": "Public company-board discovery is available only for configured Greenhouse and Lever boards. Resume upload and application submission remain disabled until secure user accounts, private storage, consent, and approved workflows are implemented."
    }


@app.post("/api/v1/search")
async def search_jobs(request: JobSearchRequest):
    return await search_public_company_boards(
        query=request.query,
        location=request.location,
        limit=request.limit,
    )
