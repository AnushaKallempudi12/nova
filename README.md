# Nova — Career Intelligence

Nova is a responsive AI-assisted job-search workspace. It helps candidates organize their resume, preferences, target platforms, and job-search workflow.

## Current MVP status
- Responsive React + Vite interface.
- Resume file selection and local preview metadata (the file is **not uploaded**).
- Platform-by-platform selection, saved in this browser with localStorage.
- Separate job-discovery and application capability labels.
- FastAPI service exposing health, platform metadata, configuration, and public company-board search endpoints.
- Initial read-only Greenhouse and Lever adapters for published job listings, activated only for board/site identifiers configured by the operator.

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

Frontend defaults to `http://localhost:5173`; API defaults to `http://localhost:8000`. Set `VITE_API_BASE_URL` in the frontend environment when the API is hosted elsewhere. Set `NOVA_ALLOWED_ORIGINS` in the backend environment to a comma-separated list of trusted frontend origins. Nova includes a starter Greenhouse employer list: Coinbase, Stripe, DoorDash, Airbnb, Discord, Robinhood, Datadog, Anduril Industries, and SpaceX. These were selected as technology employers with public Greenhouse boards, not as a promise that each currently has a role matching every skill. Live availability is checked when a search runs. Override the starter list by setting `GREENHOUSE_BOARD_TOKENS` to a comma-separated list; set it to an empty value only if you intentionally want no Greenhouse boards. Add `LEVER_SITE_NAMES` for additional Lever employers. The backend validates identifiers and caps each provider list at 25 boards. The initial title filter excludes senior, staff, principal, lead, manager, director, and architect roles to better target early-career opportunities.

## Integration roadmap
1. Add and maintain an employer board registry for public Greenhouse and Lever listings.
2. Add additional source-specific adapters only where provider terms and API access permit them.
3. Add sign-in, private resume storage, and explicit consent before any resume leaves the browser.
4. Add matching and saved-job workflows; keep application submission manual unless an authorized provider integration explicitly supports it.

The frontend now checks the FastAPI `/health` and `/api/v1/platforms` endpoints on load and shows whether the API is reachable. The job discovery panel calls `POST /api/v1/search` and renders normalized, published Greenhouse/Lever results. No applications are submitted.

## Before public production use
Add authentication and per-user authorization, private resume storage, encryption and retention controls, database-backed preferences, rate limits, audit logging, approved job-source integrations, secure secrets management, and tests. Never submit applications or answer eligibility questions without explicit user authorization and verified user-provided information.
