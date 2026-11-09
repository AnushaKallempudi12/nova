from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Nova Career Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

PLATFORMS = [
    {"id": "linkedin", "name": "LinkedIn", "search": "Limited", "application": "Manual"},
    {"id": "indeed", "name": "Indeed", "search": "Limited", "application": "Manual"},
    {"id": "glassdoor", "name": "Glassdoor", "search": "Limited", "application": "Manual"},
    {"id": "ziprecruiter", "name": "ZipRecruiter", "search": "Limited", "application": "Manual"},
    {"id": "dice", "name": "Dice", "search": "Limited", "application": "Manual"},
    {"id": "wellfound", "name": "Wellfound", "search": "Limited", "application": "Manual"},
    {"id": "career", "name": "Company career pages", "search": "Potential", "application": "Assisted"},
    {"id": "other", "name": "Other supported portals", "search": "Depends", "application": "Depends"},
]

@app.get("/")
def root():
    return {"name": "Nova Career Intelligence API", "status": "preview", "version": "0.1.0"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/platforms")
def get_platforms():
    return {"platforms": PLATFORMS}

@app.get("/api/v1/config")
def get_config():
    return {
        "resume_upload_enabled": False,
        "live_job_search_enabled": False,
        "application_submission_enabled": False,
        "message": "Preview mode. Configure authentication, secure storage, and approved provider integrations before enabling these capabilities."
    }
