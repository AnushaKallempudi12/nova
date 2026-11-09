# Nova — Career Intelligence

Nova is a responsive job-search workspace with a **verify-first, one-application pilot**. It searches configured public employer job boards, checks the exact job against the live provider feed, and only then offers a guided path to the employer's application page.

## Current pilot capabilities
- Responsive React + Vite interface, served by FastAPI from one Railway service.
- Resume selection stays in the browser. Nova does not upload or store the resume.
- Individually selectable job sources and locally saved preferences.
- Read-only search of configured Greenhouse and Lever public employer boards.
- Exact job-ID, title, employer-board, and application-URL recheck against the live public provider feed.
- Curated company-domain reachability check for the initial employer registry.
- Scam-signal warnings for payment requests, gift cards, money transfers, and messaging-only interview instructions in the published description.
- One-at-a-time pilot flow for a listing that passes the source checks. The user opens and submits on the employer's application page.

## Verification limits
A "Verified source" result means Nova matched the exact job to the employer's live public ATS feed, confirmed the expected ATS destination, and reached the curated company website. It is **not a guarantee** that every recruiter, email, message, or interview contact is genuine. Nova does not verify recruiter identity, conduct background checks, or certify that an employer is safe. A listing that cannot be independently checked is marked "Needs review"; a mismatch or strong scam signal is blocked as "High risk".

Never pay to apply, deposit a check, buy gift cards, or share banking credentials or sensitive identity data with an unverified contact. Verify recruiter contact details through the company's official website before sharing personal information.

## Pilot safety
- Automated application submission is disabled.
- Nova never answers work-authorization, sponsorship, demographic, or eligibility questions on the user's behalf.
- The user reviews every application answer and submits directly on the employer's website.
- Resume files are not sent to Nova's backend. Upload the file directly to the employer's portal only after checking the destination.
- The "I submitted this application" control records only the user's own confirmation in the current browser session; Nova does not confirm receipt from the employer.

## Supported job sources
The starter Greenhouse board registry currently includes Coinbase, Stripe, DoorDash, Airbnb, Discord, Robinhood, Datadog, Anduril Industries, and SpaceX. This is a configurable starter list, not a guarantee that each employer has a current matching vacancy. Live availability is checked at search time. Override it with `GREENHOUSE_BOARD_TOKENS`; add Lever site identifiers with `LEVER_SITE_NAMES`. Each list is capped at 25 valid identifiers.

Other platform selections (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Wellfound, and other portals) remain unconnected until an approved integration is implemented. Nova does not scrape sites or bypass their terms.

## Deploy to Railway

The repository includes a root `Dockerfile` and `railway.json`. Railway should deploy the repository root as one service:
- Builder: Dockerfile (configured by `railway.json`).
- Health check: `/health`.
- The container builds the React frontend and serves it from FastAPI.
- The API and frontend share one origin, so no frontend API URL variable is required.

Optional backend variables:
- `GREENHOUSE_BOARD_TOKENS`: comma-separated Greenhouse board identifiers. If omitted, the starter registry is used.
- `LEVER_SITE_NAMES`: comma-separated Lever site identifiers.
- `NOVA_ALLOWED_ORIGINS`: optional comma-separated CORS origins; same-origin production requests do not require it.

After deployment, open the Railway-generated public domain and check `/health`. The root page should display Nova. The API docs are available at `/docs`.

## Run locally

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Backend (in a second terminal):
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The local Vite frontend uses `http://localhost:8000` for API calls by default. For local integrated production-style testing, build the frontend and run the API from the repository root.

## Roadmap after the first pilot
1. Review the first application flow and fix usability or verification gaps.
2. Add authenticated accounts and private, encrypted resume handling only if needed.
3. Add transparent resume-to-job matching and application tracking.
4. Connect additional job platforms only through approved APIs, partner feeds, or user-directed workflows.
5. Consider application automation only where the provider explicitly permits it and the user authorizes each submission.
