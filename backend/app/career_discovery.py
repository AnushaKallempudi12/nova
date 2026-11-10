"""Universal discovery helpers for employer career sites.

Direct-site discovery uses public JSON-LD JobPosting data and, when configured,
Google Programmable Search Engine results restricted to an explicit employer
domain registry. It does not crawl login-only pages or bypass site controls.
"""
import asyncio
import html
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
    results = []
    for match in re.finditer(
        r'<script[^>]+type=["\\']application/ld\\+json["\\'][^>]*>(.*?)</script>',
        document or "", flags=re.IGNORECASE | re.DOTALL,
    ):
        raw = html.unescape(match.group(1)).strip()
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in _job_postings(payload):
            url = item.get("url") or source_url
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
                      f"{abs(hash(str(url))) & 0xffffffff:x}",
                "title": title[:300],
                "company": employer_name or company,
                "location": _location(item),
                "description": _text(item.get("description"))[:1600],
                "url": str(url),
                "source": "Company Career Site",
                "updated_at": item.get("datePosted"),
                "employment_type": item.get("employmentType"),
                "discovery_method": "schema.org JobPosting",
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
        return not actual or any(x in actual for x in (
            "united states", "usa", " u.s.", "remote", "california", "texas",
            "new york", "washington", "arkansas", "colorado", "massachusetts",
        ))
    return not wanted or not actual or wanted in actual


async def _google_cse(client: httpx.AsyncClient, query: str, location: str,
                     limit: int) -> tuple[list[dict], dict]:
    api_key = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_CX", "").strip()
    if not api_key or not cx:
        return [], {"provider": "Company Career Site Search", "status": "not_configured",
                    "count": 0, "message": "Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX to enable broad employer-site search."}
    domain_queries = []
    for name, site in COMPANY_CAREER_SITES.items():
        domain_queries.append(f"site:{site['domain']} {query} jobs careers")
    # Query the registered employer domains in small batches to stay within CSE limits.
    jobs = []
    statuses = []
    for name, site_query in zip(COMPANY_CAREER_SITES, domain_queries):
        try:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": api_key, "cx": cx, "q": f"{site_query} {location}",
                        "num": min(10, max(1, limit))},
            )
            response.raise_for_status()
            payload = response.json()
            company = name
            for item in payload.get("items", []):
                url = str(item.get("link") or "")
                parsed = urlparse(url)
                if parsed.scheme != "https" or not _host_matches(parsed.hostname or "", site["domain"]):
                    continue
                title = _text(item.get("title"))
                if not title or not _matches({"title": title, "description": item.get("snippet", ""),
                                               "company": company, "location": location}, query, ""):
                    continue
                jobs.append({
                    "id": f"cse:{name.lower().replace(' ', '-')}:"
                          f"{abs(hash(url)) & 0xffffffff:x}",
                    "title": title[:300], "company": company, "location": location,
                    "description": _text(item.get("snippet"))[:1200], "url": url,
                    "source": "Company Career Site", "updated_at": None,
                    "discovery_method": "Google Programmable Search",
                })
            statuses.append({"provider": "Company Career Site Search", "company": company,
                             "status": "ok", "count": len(payload.get("items", []))})
        except (httpx.HTTPError, ValueError) as exc:
            statuses.append({"provider": "Company Career Site Search", "company": name,
                             "status": "error", "count": 0, "message": str(exc)[:160]})
    return [job for job in jobs if _matches(job, query, location)][:limit], {
        "provider": "Company Career Site Search", "status": "ok", "count": len(jobs),
        "companies_checked": statuses,
    }


async def search_company_career_sites(client: httpx.AsyncClient, query: str, location: str,
                                      limit: int = 50) -> tuple[list[dict], list[dict]]:
    """Search registered official employer sites via CSE and parse public JSON-LD."""
    jobs: list[dict] = []
    statuses: list[dict] = []
    cse_jobs, cse_status = await _google_cse(client, query, location, limit)
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

    inspections = await asyncio.gather(*[
        inspect(name, site) for name, site in COMPANY_CAREER_SITES.items()
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
