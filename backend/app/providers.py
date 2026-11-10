import asyncio
import html
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .career_discovery import (
    configured_smartrecruiters_companies,
    enrich_job_matches,
    search_company_career_sites,
    search_smartrecruiters,
)

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
# Starter employers selected for broad software engineering opportunities.
# Board identifiers were publicly verified on Greenhouse; availability is rechecked live per search.
STARTER_GREENHOUSE_BOARDS = ["coinbase","stripe","airbnb","databricks","datadog","discord","figma","instacart","reddit","scaleai","cloudflare","anthropic"]
GREENHOUSE_BOARDS = list(dict.fromkeys(STARTER_GREENHOUSE_BOARDS + [
    value.strip() for value in os.getenv("GREENHOUSE_BOARD_TOKENS", "").split(",")
    if value.strip() and TOKEN_PATTERN.fullmatch(value.strip())
]))[:40]
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
    "stripe": "Stripe", "airbnb": "Airbnb", "databricks": "Databricks",
    "figma": "Figma", "instacart": "Instacart", "reddit": "Reddit",
    "scaleai": "Scale AI", "cloudflare": "Cloudflare", "anthropic": "Anthropic",
}
SENIOR_TITLE_TERMS = (
    "senior", "staff", "principal", "lead", "director", "manager",
    "architect", "head of", "vice president", "vp "
)
LEVER_SITES = list(dict.fromkeys(["spotify","gopuff","ro","swordhealth"] + [
    value.strip() for value in os.getenv("LEVER_SITE_NAMES", "").split(",")
    if value.strip() and TOKEN_PATTERN.fullmatch(value.strip())
]))[:40]


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
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
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
        return _is_us_location(actual_location) or "remote" in actual_location.lower()
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


# Ashby public job-board API. Configure public board identifiers in ASHBY_BOARD_NAMES.
# Ashby board slugs are case-sensitive in hosted URLs and API paths.
ASHBY_BOARDS=list(dict.fromkeys([v.lower() for v in ["ramp","vanta","linear","watershed","replit","modal","baseten","browserbase","notion","perplexity","cohere","zip","sierra","decagon","cursor"]]+[v.strip().lower() for v in os.getenv("ASHBY_BOARD_NAMES","").split(",") if v.strip() and TOKEN_PATTERN.fullmatch(v.strip())]))[:40]

async def _ashby(client:httpx.AsyncClient,board:str,query:str,location:str):
    response=await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true")
    response.raise_for_status()
    payload=response.json()
    jobs=[]
    for item in payload.get("jobs",[]):
        job_url=item.get("jobUrl") or item.get("applyUrl") or ""
        parsed=urlparse(job_url)
        if parsed.scheme.lower()!="https" or (parsed.hostname or "").lower()!="jobs.ashbyhq.com":
            continue
        job={"id":f"ashby:{board}:{item.get('id')}","title":item.get("title","Untitled role"),"company":item.get("companyName") or board.title(),"location":item.get("location","") or ("Remote" if item.get("isRemote") else ""),"description":_plain_text(item.get("descriptionPlain") or item.get("descriptionHtml") or "")[:1200],"url":job_url,"source":"Ashby","updated_at":item.get("publishedAt")}
        if _matches(job,query,location):
            jobs.append(job)
    return jobs,{"provider":"Ashby","board":board,"status":"ok","count":len(jobs)}

async def _confirm_job_page(client: httpx.AsyncClient, job: dict) -> bool:
    """Confirm the public application destination without allowing cross-host redirects."""
    provider_hosts = {
        "Greenhouse": {"boards.greenhouse.io", "job-boards.greenhouse.io"},
        "Lever": {"jobs.lever.co"},
        "Ashby": {"jobs.ashbyhq.com"},
        "SmartRecruiters": {"jobs.smartrecruiters.com", "careers.smartrecruiters.com"},
    }.get(job.get("source"), set())
    parsed = urlparse(job.get("url") or "")
    allowed_host = (job.get("allowed_host") or "").lower()
    initial_host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or not initial_host:
        return False
    allowed = initial_host in provider_hosts or (
        allowed_host and (initial_host == allowed_host or initial_host.endswith("." + allowed_host))
    )
    if not allowed:
        return False
    try:
        response = await client.get(job["url"], follow_redirects=True)
        final = urlparse(str(response.url))
        final_host = (final.hostname or "").lower()
        same_trusted_host = (
            final_host in provider_hosts
            or (allowed_host and (final_host == allowed_host or final_host.endswith("." + allowed_host)))
            or (initial_host in provider_hosts and final_host == initial_host)
        )
        return response.status_code < 400 and final.scheme.lower() == "https" and bool(same_trusted_host)
    except (httpx.HTTPError, asyncio.TimeoutError, KeyError):
        return False


async def search_public_company_boards(
    query: str,
    location: str,
    limit: int = 50,
    selected_platforms: list[str] | None = None,
    user_skills: list[str] | None = None,
) -> dict:
    """Search all selected live feeds plus registered official career sites."""
    platform_names = {
        "linkedin": "LinkedIn", "indeed": "Indeed", "dice": "Dice",
        "wellfound": "Wellfound", "builtin": "Built In",
        "ziprecruiter": "ZipRecruiter", "glassdoor": "Glassdoor",
        "monster": "Monster", "handshake": "Handshake", "usajobs": "USAJOBS",
        "flexjobs": "FlexJobs", "weworkremotely": "We Work Remotely",
        "career": "Company career websites", "other": "Other supported portals",
    }
    selected = set(selected_platforms if selected_platforms is not None else
                   ["greenhouse", "lever", "ashby", "smartrecruiters", "career"])
    provider_selection = {
        "Greenhouse": ("greenhouse" in selected, GREENHOUSE_BOARDS),
        "Lever": ("lever" in selected, LEVER_SITES),
        "Ashby": ("ashby" in selected, ASHBY_BOARDS),
        "SmartRecruiters": ("smartrecruiters" in selected, configured_smartrecruiters_companies()),
    }
    external = [platform_names[key] for key in sorted(selected) if key in platform_names]
    configured = sum(len(boards) for enabled, boards in provider_selection.values() if enabled)
    direct_sites_enabled = bool({"career", "all"} & selected)
    live_ats_enabled = any(enabled for enabled, _ in provider_selection.values())
    if not direct_sites_enabled and not live_ats_enabled:
        return {
            "jobs": [], "sources_checked": [], "configured_sources": 0,
            "external_platforms": external,
            "message": "Select All company websites or at least one connected ATS source to search live jobs.",
        }

    timeout = httpx.Timeout(14.0, connect=5.0)
    semaphore = asyncio.Semaphore(6)
    jobs: list[dict] = []
    statuses: list[dict] = []
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"Accept": "application/json,text/html,*/*",
                 "User-Agent": "Mozilla/5.0 NovaCareerSearch/1.0"},
    ) as client:
        async def call(provider: str, identifier: str):
            async with semaphore:
                try:
                    if provider == "Greenhouse":
                        return await _greenhouse(client, identifier, query, location)
                    if provider == "Lever":
                        return await _lever(client, identifier, query, location)
                    if provider == "Ashby":
                        return await _ashby(client, identifier, query, location)
                    rows, source_statuses = await search_smartrecruiters(client, query, location, [identifier], limit)
                    return rows, (source_statuses[0] if source_statuses else {
                        "provider": "SmartRecruiters", "company": identifier, "status": "ok", "count": len(rows)
                    })

        tasks = []
        for provider, (enabled, boards) in provider_selection.items():
            if not enabled:
                continue
            if not boards:
                statuses.append({
                    "provider": provider, "status": "not_configured", "count": 0,
                    "message": f"No {provider} company identifiers configured.",
                })
            else:
                tasks.extend(call(provider, board) for board in boards)

        if direct_sites_enabled:
            career_jobs, career_statuses = await search_company_career_sites(
                client, query, location, limit=max(1, min(limit, 100))
            )
            jobs.extend(career_jobs)
            statuses.extend(career_statuses)

        results = await asyncio.gather(*tasks) if tasks else []
        for rows, status in results:
            jobs.extend(rows)
            statuses.append(status)

    # Normalize duplicates across multiple sources using the canonical URL first,
    # then company/title/location as a fallback.
    unique: dict[str, dict] = {}
    for job in jobs:
        url = (job.get("url") or "").split("?")[0].rstrip("/").lower()
        fallback = "|".join(str(job.get(key, "")).strip().lower()
                            for key in ("company", "title", "location"))
        key = url or fallback
        if key not in unique:
            unique[key] = job
    jobs = list(unique.values())
    jobs.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)

    # Verify real destination pages. The first batch is checked before filtering;
    # over-fetching is intentionally bounded to avoid hammering employer sites.
    candidates = jobs[:max(1, min(limit * 2, 150))]
    availability_timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(
        timeout=availability_timeout,
        headers={"Accept": "text/html,application/xhtml+xml",
                 "User-Agent": "Mozilla/5.0 NovaJobAvailability/1.0"},
        follow_redirects=True,
    ) as page_client:
        checks = await asyncio.gather(*[
            _confirm_job_page(page_client, job) for job in candidates
        ])
    checked_jobs = [job for job, available in zip(candidates, checks) if available]
    checked_jobs = enrich_job_matches(checked_jobs, user_skills or [])[:max(1, min(limit, 100))]
    excluded = len(checks) - sum(1 for value in checks if value)
    return {
        "jobs": checked_jobs,
        "sources_checked": statuses,
        "configured_sources": configured,
        "external_platforms": external,
        "availability_checked": len(checks),
        "unavailable_or_unconfirmed": excluded,
        "message": (
            f"Found {len(jobs)} unique listings across selected sources. "
            f"Showing {len(checked_jobs)} with reachable official application pages; "
            f"excluded {excluded} unavailable or unconfirmed links."
        ),
    }
