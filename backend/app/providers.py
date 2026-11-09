import asyncio
import html
import os
import re
from typing import Any

import httpx

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
# Starter employers selected for broad software engineering opportunities.
# Board identifiers were publicly verified on Greenhouse; availability is rechecked live per search.
STARTER_GREENHOUSE_BOARDS = ["coinbase"]  # one-employer pilot; expand only after the first application is reviewed
GREENHOUSE_BOARDS = [
    value.strip() for value in os.getenv(
        "GREENHOUSE_BOARD_TOKENS", ",".join(STARTER_GREENHOUSE_BOARDS)
    ).split(",")
    if value.strip() and TOKEN_PATTERN.fullmatch(value.strip())
][:25]
COMPANY_NAMES = {
    "coinbase": "Coinbase",
    "stripe": "Stripe",
    "doordashusa": "DoorDash",
    "airbnb": "Airbnb",
    "discord": "Discord",
    "robinhood": "Robinhood",
    "datadog": "Datadog",
    "andurilindustries": "Anduril Industries",
    "spacex": "SpaceX",
}
SENIOR_TITLE_TERMS = (
    "senior", "staff", "principal", "lead", "director", "manager",
    "architect", "head of", "vice president", "vp "
)
LEVER_SITES = [
    value.strip() for value in os.getenv("LEVER_SITE_NAMES", "").split(",")
    if value.strip() and TOKEN_PATTERN.fullmatch(value.strip())
][:25]


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = html.unescape(value)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", decoded)).strip()


US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
}
US_STATE_CODES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC",
}


def _is_us_location(value: str) -> bool:
    normalized = re.sub(r"\\s+", " ", (value or "").strip().lower())
    if not normalized:
        return False
    if any(marker in normalized for marker in (
        "united states", "united states of america", " usa", "usa ",
        "u.s.", "remote - us", "remote, us", "remote (us)",
    )):
        return True
    if normalized in {"us", "usa", "remote us", "remote - usa"}:
        return True
    if any(state in normalized for state in US_STATE_NAMES):
        return True
    # Only accept a two-letter state abbreviation as a distinct comma-delimited
    # token, avoiding false positives such as the word "in" in "Remote in Europe".
    tokens = [part.strip().upper() for part in normalized.split(",")]
    return any(token in US_STATE_CODES for token in tokens[1:])


def _matches(job: dict[str, Any], query: str, location: str) -> bool:
    searchable = " ".join(str(job.get(key, "")) for key in ("title", "description", "company")).lower()
    phrases = [part.strip().lower() for part in query.split(",") if part.strip()]
    if phrases and not any(phrase in searchable for phrase in phrases):
        return False
    title = str(job.get("title", "")).lower()
    if any(term in title for term in SENIOR_TITLE_TERMS):
        return False
    wanted_location = location.strip().lower()
    actual_location = str(job.get("location", ""))
    if wanted_location in {"united states", "usa", "us"}:
        return _is_us_location(actual_location)
    if wanted_location and wanted_location not in actual_location.lower():
        return False
    return True

async def _greenhouse(client: httpx.AsyncClient, board: str, query: str, location: str) -> tuple[list[dict], dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    response = await client.get(url)
    response.raise_for_status()
    payload = response.json()
    jobs = []
    for item in payload.get("jobs", []):
        location_name = (item.get("location") or {}).get("name", "")
        job = {
            "id": f"greenhouse:{board}:{item.get('id')}",
            "title": item.get("title", "Untitled role"),
            "company": COMPANY_NAMES.get(board, board.replace("-", " ").replace("_", " ").title()),
            "location": location_name,
            "description": _plain_text(item.get("content", ""))[:1200],
            "url": item.get("absolute_url", ""),
            "source": "Greenhouse",
            "updated_at": item.get("updated_at"),
        }
        if job["url"].startswith("https://") and _matches(job, query, location):
            jobs.append(job)
    return jobs, {"provider": "Greenhouse", "board": board, "status": "ok", "count": len(jobs)}


async def _lever(client: httpx.AsyncClient, site: str, query: str, location: str) -> tuple[list[dict], dict]:
    url = f"https://api.lever.co/v0/postings/{site}?mode=json"
    response = await client.get(url)
    response.raise_for_status()
    payload = response.json()
    jobs = []
    for item in payload if isinstance(payload, list) else []:
        categories = item.get("categories") or {}
        job = {
            "id": f"lever:{site}:{item.get('id')}",
            "title": item.get("text", "Untitled role"),
            "company": site.replace("-", " ").replace("_", " ").title(),
            "location": categories.get("location", ""),
            "description": _plain_text(item.get("descriptionPlain") or item.get("description", ""))[:1200],
            "url": item.get("hostedUrl") or item.get("applyUrl") or "",
            "source": "Lever",
            "updated_at": item.get("createdAt"),
        }
        if job["url"].startswith("https://") and _matches(job, query, location):
            jobs.append(job)
    return jobs, {"provider": "Lever", "site": site, "status": "ok", "count": len(jobs)}


async def search_public_company_boards(query: str, location: str, limit: int = 50) -> dict:
    jobs: list[dict] = []
    statuses: list[dict] = []
    configured = len(GREENHOUSE_BOARDS) + len(LEVER_SITES)
    if not configured:
        return {
            "jobs": [],
            "sources_checked": [],
            "configured_sources": 0,
            "message": "No company career boards are configured yet. Add Greenhouse board tokens and/or Lever site names to the backend environment."
        }

    timeout = httpx.Timeout(12.0, connect=5.0)
    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(timeout=timeout, headers={"Accept": "application/json", "User-Agent": "NovaCareerSearch/0.1"}) as client:
        async def safe_call(provider: str, identifier: str):
            async with semaphore:
                try:
                    if provider == "Greenhouse":
                        return await _greenhouse(client, identifier, query, location)
                    return await _lever(client, identifier, query, location)
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    return [], {"provider": provider, "board": identifier, "status": "error", "message": str(exc)[:180]}

        tasks = [safe_call("Greenhouse", token) for token in GREENHOUSE_BOARDS]
        tasks += [safe_call("Lever", site) for site in LEVER_SITES]
        results = await asyncio.gather(*tasks)

    for source_jobs, status in results:
        jobs.extend(source_jobs)
        statuses.append(status)

    jobs.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return {
        "jobs": jobs[:max(1, min(limit, 100))],
        "sources_checked": statuses,
        "configured_sources": configured,
        "message": f"Found {len(jobs)} matching published roles across configured public career boards."
    }
