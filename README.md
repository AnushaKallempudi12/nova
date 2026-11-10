# Nova — Career Intelligence

Nova is a private job-search workspace with authenticated accounts, saved resumes, job-source discovery, cover-letter drafts and application tracking.

## Features

- Email/password and Google sign-in through Supabase Auth.
- Account-scoped PostgreSQL records for profile details, extracted resume text, job preferences, applications and generated cover letters.
- Optional profile fields; users can skip anything they do not want to provide.
- Resume parsing for text-based PDF and DOCX files (10 MB maximum). The original upload is processed in memory; extracted resume text and detected skills are saved to the account database.
- Expanded job-source catalog: LinkedIn, Indeed, Dice, Wellfound, Built In, ZipRecruiter, Glassdoor, Monster, Handshake, USAJOBS, FlexJobs, We Work Remotely, and employer ATS career pages.
- Live public employer-board search across Greenhouse, Lever, Ashby and optional SmartRecruiters company boards.
- Universal employer career-site discovery across a starter registry including Google, Apple, Amazon, Microsoft, Walmart, Meta, NVIDIA, Adobe, Salesforce and IBM. Public schema.org JobPosting data is extracted when the employer page exposes it.
- Optional Tavily Search integration discovers role-specific listings on employer career sites and recognized ATS hosts. Searching for a named company also supports employers outside the starter registry. Configure `TAVILY_API_KEY` on the backend; without it, Nova continues using direct ATS feeds and public JobPosting structured data.
- Additional official career sites can be registered with `NOVA_CAREER_SITES`; this avoids pretending every company exposes a common public API.
- Editable cover-letter drafts generated from saved resume details and job-description keywords. Drafts are saved to the user's account. The generator is template-based and does not claim to use a hosted AI model.
- Authenticated application tracker and dashboard.
- Nova Apply preparation flow: verified jobs can create an account-scoped application draft, prefill saved profile details, request review, and create/update the Dashboard record automatically.
- Optional Chrome/Chromium browser extension that fills supported employer form fields after the user explicitly clicks Autofill. Sensitive eligibility questions and resume file uploads remain manual.
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
- Optional: `GREENHOUSE_BOARD_TOKENS`, `LEVER_SITE_NAMES`, `ASHBY_BOARD_NAMES`, `SMARTRECRUITERS_COMPANIES`
- Optional broader career-site discovery: `TAVILY_API_KEY`
- Optional custom employer registry: `NOVA_CAREER_SITES` (JSON object of company names to official domain and HTTPS career-page URL)

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
- `SMARTRECRUITERS_COMPANIES`: comma-separated public SmartRecruiters company identifiers.
- `TAVILY_API_KEY`: enables broader role-specific discovery across public employer career pages and recognized ATS hosts, including companies outside the starter registry.
- `NOVA_CAREER_SITES`: optional JSON object, for example `{"Example Corp":{"domain":"example.com","url":"https://careers.example.com"}}`. Only HTTPS URLs are accepted. Nova reads public structured job data; pages that render listings only in client-side scripts may not expose jobs to this fallback.

LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice, Wellfound and other external portals remain official external destinations unless a permitted direct integration is configured. The career-site crawler only reads public pages and structured job data; it does not log in, bypass CAPTCHAs, or defeat access controls. Coverage varies by employer website.

## Nova Apply and application safety

Selecting Apply with Nova creates or updates an application record automatically and opens an editable review of saved profile information. The optional local browser extension can fill supported text, email, phone, textarea and select fields on the employer's current page after the user clicks its toolbar action. The extension never submits an application, never stores employer passwords, never overwrites non-empty fields, and deliberately skips work authorization, visa, sponsorship, demographic, salary and other sensitive questions. Users attach their resume file manually because Nova retains extracted resume text rather than the original upload. After submitting on the employer website, users can confirm the outcome in Nova to mark the Dashboard record Submitted. This confirmation is user-reported, not an independently verified employer receipt.

Install and use the extension by following `browser-extension/README.md`. Job matching currently reports exact resume-skill keyword overlap, not a semantic or validated prediction. Results show matched resume skills so users can understand the score.

## Local development

Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`

Frontend: `cd frontend && npm install && npm run dev`

Configure the environment variables above before testing authenticated flows.


## AI cover letter generation

Nova's Cover Letter Studio uses the candidate's saved resume text, saved experience summary, and the full job description to create an editable letter with a minimum of 250 words and no maximum. It prioritizes concrete, verified experience and avoids inventing qualifications, achievements, metrics, or company initiatives. When Tavily search is configured, Nova can add a small set of attributable company research snippets and displays the source links beside the draft. If reliable company information is not found, the generator does not fabricate it.

The backend supports Google Gemini and OpenAI. Configure `GEMINI_API_KEY` in the Railway backend to use Gemini; it is selected by default when present. The optional provider selector is `NOVA_AI_PROVIDER=gemini` (or `openai` / `auto`), and the Gemini model override is `NOVA_GEMINI_MODEL` (default `gemini-2.5-flash`). OpenAI remains optional through `NOVA_OPENAI_API_KEY` (or `OPENAI_API_KEY`) and `NOVA_COVER_LETTER_MODEL` (default `gpt-4.1-mini`). Optional company research uses `TAVILY_API_KEY`. Never commit real API keys to the repository.

Before generation, the user must explicitly consent in Cover Letter Studio to sending their saved resume text, profile summary, and job description to the configured AI provider. Only company name and target role are sent to Tavily Search for company research. Generated drafts are saved to the user's account and remain editable; the user must verify the facts and approve the final letter before submitting it.

 
## Company career-site search configuration

Live ATS feeds (Greenhouse, Lever, Ashby and configured SmartRecruiters boards) do not require Google search credentials. Broader discovery of jobs hosted on employer career websites requires Google Programmable Search Engine credentials because many career pages render job listings dynamically rather than exposing public JobPosting JSON-LD on their landing page.

Add both variables to the **Nova backend** Railway service:
- `GOOGLE_CSE_API_KEY` — Google Programmable Search API key.
- `GOOGLE_CSE_CX` — Programmable Search Engine ID configured to search the web or the desired employer domains.

Without both variables, Nova can still inspect registered career landing pages for structured JobPosting data, but results may be limited or empty. The UI now reports this limitation rather than implying that every employer career site has a live feed.
