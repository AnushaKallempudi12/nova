# Nova — Career Intelligence

Nova is a responsive job-search workspace with separate pages for Overview, Dashboard, Applications, Resumes, Job Platforms, and More Tools.

## MVP features

- Multi-page desktop and mobile navigation; the home page is an introduction and quick-start workspace rather than one long scrolling page.
- Dashboard totals for Applied, Pending, Responded, Rejected, Interviews, Offers, and response activity.
- Expandable application tracker with company, role, status, platform, dates, notes, filters, create, edit, and delete.
- Resume upload and text extraction for PDF and DOCX files (10 MB maximum). Nova identifies common skills and resume-section references for the user to review.
- Resume text is extracted in memory by the API. The original uploaded file is not retained; the extracted profile is stored in this browser's local storage.
- Job search against configured public Greenhouse and Lever boards, with exact listing verification before opening an employer application destination.
- Resume keyword overlap shown on job cards as a basic relevance signal, not a validated or predictive match score.
- Job platform catalog for LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Wellfound, company career pages, and other supported portals. Platform selection is not the same as an account connection or active API integration.
- More Tools area for job preferences, application limits, privacy information, and help.

## Current integration limits

The backend searches only the public Greenhouse and Lever boards configured through environment variables. The starter Greenhouse board is Coinbase. Add additional identifiers through `GREENHOUSE_BOARD_TOKENS` and `LEVER_SITE_NAMES` after validating each board. Search results are not a comprehensive view of every job opening.

LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, and Wellfound are currently catalog entries only. Nova does not scrape those sites, collect their passwords, bypass access controls, or claim they are integrated.

## Application workflow and safety

Nova verifies a listing and opens the verified employer destination. The user completes and submits the application on the employer's website. The tracker starts at Pending for a job opened from discovery; the user should change it to Applied only after submitting. Nova does not automatically submit applications in this MVP.

Work authorization, sponsorship, demographic, and other sensitive eligibility answers must be provided and confirmed by the user. Nova does not invent answers or claim an application was received by an employer.

## Data and security limitations — read before using personal data

- Application records are stored in the database and scoped using a browser-generated workspace ID. This is **not authentication**; it is not safe multi-user access control.
- Resume extracted text is kept in local storage in the current browser. Clearing browser storage removes the local profile.
- The original uploaded resume is processed in memory and not saved as an uploaded file.
- For durable application records on Railway, set `DATABASE_URL` to the Railway PostgreSQL connection string. SQLite on Railway's ephemeral filesystem is not durable across redeployments.
- Do not use this MVP for sensitive personal data or expose it as a secure multi-user service until real user authentication, per-user authorization, encrypted storage, and appropriate retention controls are implemented.

## Railway deployment

The existing Railway setup uses two services from this repository:

**Backend service**
- Root directory: `/backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Set `DATABASE_URL` to Railway PostgreSQL.
- Set `NOVA_ALLOWED_ORIGINS` to the frontend Railway URL if the frontend and backend use separate domains.

**Frontend service**
- Root directory: `/frontend`
- Build: `npm install && npm run build`
- Start: `npm run preview -- --host 0.0.0.0 --port $PORT`
- Set `VITE_API_BASE_URL` to the backend Railway URL. This is a build-time variable; changing it requires a frontend rebuild.

Optional backend variables:
- `GREENHOUSE_BOARD_TOKENS`: comma-separated Greenhouse board identifiers.
- `LEVER_SITE_NAMES`: comma-separated Lever site identifiers.
- `NOVA_ALLOWED_ORIGINS`: comma-separated frontend origins.

## Local development

Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

The local frontend calls `http://localhost:8000` by default. API documentation is available at `/docs`.

## Next hardening steps

1. Add real account authentication and enforce per-user ownership on every API.
2. Add durable, private resume storage only after access control and retention rules are in place.
3. Improve resume parsing and explainable skill/job matching.
4. Add integrations only through approved APIs, partner feeds, or user-directed workflows.
5. Enable rule-based automatic submission only for providers that explicitly permit it, with user authorization and sensitive-answer safeguards.
