# Nova — Career Intelligence

Nova is a private job-search workspace with authenticated accounts, saved resumes, job-source discovery, cover-letter drafts and application tracking.

## Features

- Email/password and Google sign-in through Supabase Auth.
- Account-scoped PostgreSQL records for profile details, extracted resume text, job preferences, applications and generated cover letters.
- Optional profile fields; users can skip anything they do not want to provide.
- Resume parsing for text-based PDF and DOCX files (10 MB maximum). The original upload is processed in memory; extracted resume text and detected skills are saved to the account database.
- Expanded job-source catalog: LinkedIn, Indeed, Dice, Wellfound, Built In, ZipRecruiter, Glassdoor, Monster, Handshake, USAJOBS, FlexJobs, We Work Remotely, and employer ATS career pages.
- Live public employer-board search across a starter set of Greenhouse, Lever and Ashby employer boards, plus additional board identifiers configured by the owner. Other job platforms are official external links, not falsely described as API integrations.
- Editable cover-letter drafts generated from saved resume details and job-description keywords. Drafts are saved to the user's account. The generator is template-based and does not claim to use a hosted AI model.
- Authenticated application tracker and dashboard.
- Larger typography and clearer responsive controls.

## Required configuration before first launch

### Supabase project

Create a Supabase project, then:

1. Enable Email authentication.
2. Enable the Google provider and configure Google OAuth client credentials in Supabase.
3. Add your Nova frontend URL to Supabase's allowed redirect URLs. Use the frontend origin as the OAuth redirect target.
4. Copy the Supabase project URL and anon/public key.
5. Copy the PostgreSQL connection string from Supabase Database settings. Prefer the pooler connection string for hosted application use if your deployment environment requires it.

Set these variables in Railway:

**Backend service**
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `DATABASE_URL` (Supabase PostgreSQL connection string)
- `NOVA_ALLOWED_ORIGINS` (Nova frontend URL)
- Optional: `GREENHOUSE_BOARD_TOKENS`, `LEVER_SITE_NAMES`, `ASHBY_BOARD_NAMES`

**Frontend service — build-time variables**
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_API_BASE_URL` (Nova backend URL)

Use only the Supabase anon/public key in the frontend. Never expose a Supabase service-role key or database password in frontend code, and never commit secrets to Git.

### Database and data ownership

The backend creates the new account tables on startup. Each account's profile, resume text, applications and cover letters are keyed by the authenticated Supabase user ID. API requests validate the bearer token with Supabase Auth and query only that user's records.

Existing anonymous workspace applications are not automatically migrated into an account. The old workspace-based API remains for backward compatibility, but the updated frontend uses the authenticated `/api/v2` account APIs.

The original uploaded resume file is not retained. Only extracted text, filename and detected skills are stored. Users should review extracted text and generated cover letters before using them.

## Job-source coverage

- `GREENHOUSE_BOARD_TOKENS`: comma-separated public Greenhouse board identifiers.
- `LEVER_SITE_NAMES`: comma-separated public Lever site identifiers.
- `ASHBY_BOARD_NAMES`: comma-separated public Ashby board identifiers.

LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Wellfound and other external portals are official search destinations in the catalog; they are not represented as direct API integrations. Nova does not scrape them, collect their passwords or bypass access controls.

## Application safety

Nova does not automatically submit applications. Users complete employer forms and confirm submission before changing a tracker record to Applied. Work authorization, sponsorship, demographic and legal declarations must be answered and approved by the user. Job matching uses basic keyword overlap and is not a validated prediction.

## Local development

Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`

Frontend: `cd frontend && npm install && npm run dev`

Configure the environment variables above before testing authenticated flows.
