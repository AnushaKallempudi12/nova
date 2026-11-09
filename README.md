# Nova — Career Intelligence

Nova is a responsive AI-assisted job-search workspace. It helps candidates organize their resume, preferences, target platforms, and job-search workflow.

## Current MVP status
- Responsive React + Vite interface.
- Resume file selection and local preview metadata (the file is **not uploaded**).
- Platform-by-platform selection, saved in this browser with localStorage.
- Separate job-discovery and application capability labels.
- FastAPI service exposing health, platform metadata, and configuration endpoints.

**Important:** This repository does not yet contain live job-board integrations, authenticated accounts, server-side resume storage, or application-submission automation. Platform labels describe the intended workflow, not a connected integration. Nova must use provider-approved APIs/feeds and respect each site's terms. Where an approved application integration is unavailable, users must apply directly on the provider's site.

## Platforms
LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Wellfound, company career pages, and other supported portals. Capability is provider- and integration-dependent.

## Run locally

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend defaults to `http://localhost:5173`; API defaults to `http://localhost:8000`.

## Before public production use
Add authentication and per-user authorization, private resume storage, encryption and retention controls, database-backed preferences, rate limits, audit logging, approved job-source integrations, secure secrets management, and tests. Never submit applications or answer eligibility questions without explicit user authorization and verified user-provided information.
