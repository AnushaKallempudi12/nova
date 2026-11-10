"""Universal discovery helpers for employer career sites.

Direct-site discovery uses public JSON-LD JobPosting data and, when configured,
Google Programmable Search Engine results restricted to an explicit employer
domain registry. It does not crawl login-only pages or bypass site controls.
"""
import asyncio
import html
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

COMPANY_CAREER_SITES = {
    "Google": {"domain": "google.com", "url": "https://careers.google.com/jobs/results/"},
    "Apple": {"domain": "apple.com", "url": "https://jobs.apple.com/en-us/search"},
    "Amazon": {"domain": "amazon.jobs", "url": "https://www.amazon.jobs/en/search"},
    "Microsoft": {"domain": "microsoft.com", "url": "https://careers.microsoft.com/v2/global/en/home.html"},
    "Walmart": {"domain": "walmart.com", "url": "https://careers.walmart.com/"},
    "Meta": {"domain": "metacareers.com", "url": "https://www.metacareers.com/jobs/"},
    "NVIDIA": {"domain": "nvidia.com", "url": "https://www.nvidia.com/en-us/about-nvidia/careers/"},
    "Adobe": {"domain": "adobe.com", "url": "https://careers.adobe.com/"},
    "Salesforce": {"domain": "salesforce.com", "url": "https://careers.salesforce.com/"},
    "IBM": {"domain": "ibm.com", "url": "https://www.ibm.com/careers/search"},
}
# Optional JSON object: {"Company":{"domain":"company.com","url":"https://careers.company.com"}}
try:
    _custom_sites = json.loads(os.getenv("NOVA_CAREER_SITES", "{}"))
    if isinstance(_custom_sites, dict):
        for _name, _site in _custom_sites.items():
            if isinstance(_site, dict) and _site.get("domain") and _site.get("url"):
                _parsed = urlparse(str(_site["url"]))
                if _parsed.scheme == "https" and _parsed.hostname:
                    COMPANY_CAREER_SITES[str(_name)[:100]] = {
                        "domain": str(_site["domain"]).lower(),
                        "url": str(_site["url"]),
                    }
except (TypeError, ValueError):
    pass


def _host_matches(host: str, domain: str) -> bool:
    host = (host or "").lower().rstrip(".")
    domain = (domain or "").lower().rstrip(".")
    return bool(host and domain and (host == domain or host.endswith("." + domain)))


def _text(value: Any) -> str:
    if value is None:
        return ""
    value = html.unescape(re.sub(r"<[^>]+>", " ", str(value)))
    return re.sub(r"\s+", " ", value).strip()


def _location(job: dict[str, Any]) -> str:
    locations = job.get("jobLocation") or job.get("jobLocationType") or []
    if isinstance(locations, dict):
        locations = [locations]
    if isinstance(locations, str):
        return _text(locations)
    parts = []
    for item in locations if isinstance(locations, list) else []:
        address = item.get("address", item) if isinstance(item, dict) else {}
        if isinstance(address, str):
            parts.append(address)
            continue
        if isinstance(address, dict):
            value = ", ".join(str(address.get(k, "")).strip() for k in
                              ("addressLocality", "addressRegion", "addressCountry") if address.get(k))
            if value:
                parts.append(value)
    if job.get("jobLocationType") == "TELECOMMUTE":
        parts.append("Remote")
    return "; ".join(dict.fromkeys(parts))


def _job_postings(value: Any) -> list[dict[str, Any]]:
    found = []
    if isinstance(value, list):
        for item in value:
            found.extend(_job_postings(item))
    elif isinstance(value, dict):
        kind = value.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            found.append(value)
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in value:
                found.extend(_job_postings(value[key]))
    return found


def normalize_jsonld_jobs(document: str, company: str, source_url: str) -> list[dict[str, Any]]:
    """Extract only schema.org JobPosting records from a fetched public page."""
    from urllib.parse import urljoin

    results = []
    script_pattern = r"""<script[^>]+type=["']application/ld\+json["'][^>]*>(.*?)</script>"""
    for match in re.finditer(script_pattern, document or "", flags=re.IGNORECASE | re.DOTALL):
        raw = html.unescape(match.group(1)).strip()
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in _job_postings(payload):
            url = item.get("url") or source_url
            if str(url).startswith("/"):
                url = urljoin(source_url, str(url))
            parsed = urlparse(str(url))
            if parsed.scheme != "https" or not parsed.hostname:
                continue
            title = _text(item.get("title") or item.get("name"))
            if not title:
                continue
            employer = item.get("hiringOrganization") or {}
            employer_name = _text(employer.get("name")) if isinstance(employer, dict) else ""
            results.append({
                "id": f"career:{company.lower().replace(' ', '-')}:"
                      + hashlib.sha1(str(url).encode()).hexdigest()[:12],
                "title": title[:300],
                "company": employer_name or company,
                "location": _location(item),
                "description": _text(item.get("description"))[:1600],
                "url": str(url),
                "source": "Company Career Site",
                "updated_at": item.get("datePosted"),
                "employment_type": item.get("employmentType"),
                "discovery_method": "schema.org JobPosting",
                "allowed_host": (urlparse(str(url)).hostname or "").lower(),
            })
    return results


def _matches(job: dict[str, Any], query: str, location: str) -> bool:
    query_terms = [part.strip().lower() for part in re.split(r"[,;]", query or "") if part.strip()]
    haystack = " ".join(str(job.get(key, "")) for key in ("title", "description", "company")).lower()
    if query_terms and not any(term in haystack for term in query_terms):
        return False
    wanted = (location or "").strip().lower()
    actual = str(job.get("location", "")).lower()
    if wanted in {"united states", "usa", "us"}:
        if not actual:
            return True
        us_markers = (
            "united states", "united states of america", "usa", "u.s.", "remote",
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
        )
        if any(marker in actual for marker in us_markers):
            return True
        state_codes = {
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
            "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
            "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
            "TX","UT","VT","VA","WA","WV","WI","WY","DC",
        }
        return any(part.strip().upper() in state_codes for part in actual.split(",")[1:])
    return not wanted or not actual or wanted in actual


async def _google_cse(client: httpx.AsyncClient, query: str, location: str,
                     limit: int, company_filter: str = "") -> tuple[list[dict], dict]:
    api_key = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_CX", "").strip()
    if not api_key or not cx:
        return [], {"provider": "Company Career Site Search", "status": "not_configured",
                    "count": 0, "message": "Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX to enable broad employer-site search."}

    if company_filter.strip():
        search_query = f'"{company_filter.strip()}" {query} jobs careers {location}'
    else:
        search_query = f"{query} jobs careers {location} -site:linkedin.com -site:indeed.com -site:glassdoor.com -site:ziprecruiter.com -site:monster.com -site:dice.com -site:wellfound.com -site:careerbuilder.com"
    try:
        response = await client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cx, "q": search_query,
                    "num": min(10, max(1, limit))},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return [], {"provider": "Company Career Site Search", "status": "error",
                    "count": 0, "message": str(exc)[:160]}

    ats_hosts = (
        "boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co",
        "jobs.ashbyhq.com", "jobs.smartrecruiters.com", "careers.smartrecruiters.com",
        "myworkdayjobs.com", "icims.com", "oraclecloud.com", "workable.com",
        "recruitee.com", "teamtailor.com", "bamboohr.com",
    )
    excluded_hosts = {
        "linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com",
        "monster.com", "dice.com", "wellfound.com", "careerbuilder.com", "simplyhired.com",
        "jooble.org", "talent.com", "adzuna.com", "jobcase.com", "lensa.com",
        "builtin.com", "flexjobs.com", "weworkremotely.com",
    }
    company_token = re.sub(r"[^a-z0-9]", "", company_filter.lower())
    jobs = []
    for item in payload.get("items", []):
        url = str(item.get("link") or "")
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            continue
        if any(_host_matches(host, blocked) for blocked in excluded_hosts):
            continue
        registered_company = next((name for name, site in COMPANY_CAREER_SITES.items()
                                   if _host_matches(host, site["domain"])), None)
        is_known_ats = any(_host_matches(host, ats_host) for ats_host in ats_hosts)
        if company_filter.strip():
            host_token = re.sub(r"[^a-z0-9]", "", host)
            company_matches_host = bool(company_token and company_token in host_token)
            if not registered_company and not is_known_ats and not company_matches_host:
                continue
            company = registered_company or company_filter.strip()
        else:
            career_path = any(part in parsed.path.lower() for part in ("job", "career", "employment", "vacancy"))
            career_host = host.startswith("careers.") or host.startswith("jobs.")
            if not registered_company and not is_known_ats and not career_path and not career_host:
                continue
            if registered_company:
                company = registered_company
            else:
                meta = (item.get("pagemap") or {}).get("metatags") or []
                meta = meta[0] if meta and isinstance(meta[0], dict) else {}
                company = (meta.get("og:site_name") or meta.get("application-name")
                           or meta.get("og:title") or "")
                if not company:
                    if any(_host_matches(host, ats) for ats in ats_hosts):
                        company = parsed.path.strip("/").split("/")[0].replace("-", " ").title()
                    elif host.endswith(".myworkdayjobs.com"):
                        company = host.split(".")[0].replace("-", " ").title()
                    else:
                        company = host.split(":")[0].split(".")[0].replace("-", " ").title()

        title = _text(item.get("title"))
        snippet = _text(item.get("snippet"))
        job = {"title": title, "description": snippet, "company": company, "location": location}
        if not title or not _matches(job, query, ""):
            continue
        jobs.append({
            "id": f"cse:{re.sub(r'[^a-z0-9]+', '-', company.lower()).strip('-')}:"
                  f"{hashlib.sha1(url.encode()).hexdigest()[:12]}",
            "title": title[:300], "company": company, "location": location,
            "description": snippet[:1200], "url": url,
            "source": "Company Career Site", "updated_at": None,
            "discovery_method": "Google Programmable Search",
            "allowed_host": host,
        })
    return jobs, {"provider": "Company Career Site Search", "status": "ok",
                  "count": len(jobs), "results_returned": len(payload.get("items", [])),
                  "company_filter": company_filter or None}


async def search_company_career_sites(client: httpx.AsyncClient, query: str, location: str,
                                      limit: int = 50, company: str = "") -> tuple[list[dict], list[dict]]:
    """Search registered official employer sites via CSE and parse public JSON-LD."""
    jobs: list[dict] = []
    statuses: list[dict] = []
    cse_jobs, cse_status = await _google_cse(client, query, location, limit, company)
    jobs.extend(cse_jobs)
    statuses.append(cse_status)

    # Directly inspect each registered careers landing page for public JobPosting JSON-LD.
    # This is a best-effort fallback; many large employers render jobs client-side.
    semaphore = asyncio.Semaphore(5)

    async def inspect(company: str, site: dict[str, str]):
        async with semaphore:
            try:
                response = await client.get(site["url"], follow_redirects=True)
                final_host = urlparse(str(response.url)).hostname or ""
                if response.status_code >= 400 or not _host_matches(final_host, site["domain"]):
                    return [], {"provider": "Company Career Site", "company": company,
                                "status": "unavailable", "count": 0}
                parsed = normalize_jsonld_jobs(response.text, company, str(response.url))
                matched = [job for job in parsed if _matches(job, query, location)]
                return matched, {"provider": "Company Career Site", "company": company,
                                 "status": "ok", "count": len(matched)}
            except (httpx.HTTPError, ValueError) as exc:
                return [], {"provider": "Company Career Site", "company": company,
                            "status": "error", "count": 0, "message": str(exc)[:160]}

    inspection_sites = [(name, site) for name, site in COMPANY_CAREER_SITES.items()
                        if not company.strip() or company.strip().lower() in name.lower()]
    inspections = await asyncio.gather(*[
        inspect(name, site) for name, site in inspection_sites
    ])
    for rows, status in inspections:
        jobs.extend(rows)
        statuses.append(status)
    return jobs[:limit], statuses


async def search_smartrecruiters(client: httpx.AsyncClient, query: str, location: str,
                                 companies: list[str], limit: int = 50) -> tuple[list[dict], list[dict]]:
    """Search public SmartRecruiters postings for configured company identifiers."""
    jobs: list[dict] = []
    statuses: list[dict] = []
    semaphore = asyncio.Semaphore(5)

    async def fetch(company_id: str):
        async with semaphore:
            try:
                response = await client.get(
                    f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings",
                    params={"limit": 100, "offset": 0},
                )
                response.raise_for_status()
                payload = response.json()
                rows = []
                for item in payload.get("content", []):
                    loc = item.get("location") or {}
                    city = loc.get("city")
                    region = loc.get("region")
                    country = loc.get("country")
                    loc_text = ", ".join(str(x) for x in (city, region, country) if x)
                    job_url = item.get("ref") or item.get("applyUrl") or ""
                    parsed = urlparse(job_url)
                    if parsed.scheme != "https" or not parsed.hostname:
                        continue
                    job = {
                        "id": f"smartrecruiters:{company_id}:{item.get('id')}",
                        "title": _text(item.get("name") or item.get("title")),
                        "company": _text((payload.get("company") or {}).get("name")) or company_id,
                        "location": loc_text,
                        "description": _text(item.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", ""))[:1600],
                        "url": job_url,
                        "source": "SmartRecruiters",
                        "updated_at": item.get("releasedDate"),
                        "allowed_host": (parsed.hostname or "").lower(),
                    }
                    if job["title"] and _matches(job, query, location):
                        rows.append(job)
                return rows, {"provider": "SmartRecruiters", "company": company_id,
                              "status": "ok", "count": len(rows)}
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                return [], {"provider": "SmartRecruiters", "company": company_id,
                            "status": "error", "count": 0, "message": str(exc)[:160]}

    results = await asyncio.gather(*[fetch(company) for company in companies])
    for rows, status in results:
        jobs.extend(rows)
        statuses.append(status)
    return jobs[:limit], statuses


def configured_smartrecruiters_companies() -> list[str]:
    return list(dict.fromkeys(
        value.strip() for value in os.getenv("SMARTRECRUITERS_COMPANIES", "").split(",")
        if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value.strip())
    ))[:40]


def enrich_job_matches(jobs: list[dict], skills: list[str]) -> list[dict]:
    clean_skills = list(dict.fromkeys(s.strip() for s in skills if isinstance(s, str) and s.strip()))[:100]
    if not clean_skills:
        return jobs
    for job in jobs:
        haystack = " ".join(str(job.get(k, "")) for k in ("title", "description")).lower()
        matched = [skill for skill in clean_skills if skill.lower() in haystack]
        job["matched_skills"] = matched
        job["unmatched_profile_skills"] = [skill for skill in clean_skills if skill not in matched]
        job["match_score"] = round(len(matched) / min(len(clean_skills), 8) * 100)
        job["match_method"] = "Exact resume-skill keyword overlap"
    return jobs
