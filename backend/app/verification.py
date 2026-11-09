import asyncio
import re
from urllib.parse import urlparse

import httpx

from .providers import COMPANY_NAMES, GREENHOUSE_BOARDS, LEVER_SITES

# Curated company domains. This registry is intentionally explicit: an unknown
# company is never silently treated as verified.
COMPANY_DOMAINS = {
    "coinbase": "coinbase.com",
    "stripe": "stripe.com",
    "doordashusa": "doordash.com",
    "airbnb": "airbnb.com",
    "discord": "discord.com",
    "robinhood": "robinhood.com",
    "datadog": "datadoghq.com",
    "andurilindustries": "anduril.com",
    "spacex": "spacex.com",
}

SCAM_PATTERNS = [
    (r"\b(upfront fee|registration fee|training fee|pay to apply|payment to secure)\b", "The description mentions a fee or payment to apply."),
    (r"\b(gift cards?|wire transfer|western union|money order|deposit a check)\b", "The description mentions an unusual payment or money-transfer method."),
    (r"\b(telegram only| whatsapp only|interview only on telegram|interview only on whatsapp)\b", "The description directs applicants to messaging-only interviews."),
    (r"\b(crypto payment|cryptocurrency payment)\b", "The description mentions cryptocurrency payment."),
]


def _host_matches(host: str, domain: str) -> bool:
    host = (host or "").lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def _company_slug(job_id: str) -> tuple[str, str] | None:
    parts = job_id.split(":", 2)
    if len(parts) != 3:
        return None
    provider, slug, external_id = parts
    if not external_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", slug):
        return None
    if provider == "greenhouse" and slug in GREENHOUSE_BOARDS:
        return provider, slug
    if provider == "lever" and slug in LEVER_SITES:
        return provider, slug
    return None


async def _load_published_job(client: httpx.AsyncClient, provider: str, slug: str, external_id: str):
    if provider == "greenhouse":
        endpoint = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        response = await client.get(endpoint)
        response.raise_for_status()
        payload = response.json()
        return next((item for item in payload.get("jobs", []) if str(item.get("id")) == external_id), None)
    endpoint = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    response = await client.get(endpoint)
    response.raise_for_status()
    payload = response.json()
    return next((item for item in payload if str(item.get("id")) == external_id), None) if isinstance(payload, list) else None


async def _check_company_domain(client: httpx.AsyncClient, domain: str) -> tuple[str, str]:
    try:
        response = await client.get(f"https://{domain}/", follow_redirects=True)
        final_host = urlparse(str(response.url)).hostname or ""
        if _host_matches(final_host, domain) and response.status_code < 500:
            return "pass", f"The registered company website responded at {final_host} (HTTP {response.status_code})."
        return "review", "The registered company website did not resolve to its expected domain."
    except (httpx.HTTPError, asyncio.TimeoutError):
        return "review", "The registered company website could not be reached during this check."


async def verify_job_listing(job_id: str, submitted_url: str, submitted_title: str, submitted_company: str) -> dict:
    parsed_id = _company_slug(job_id)
    if not parsed_id:
        return {
            "status": "High risk",
            "risk_level": "high",
            "summary": "This listing does not match a currently configured, supported public employer board.",
            "checks": [{"name": "Published listing", "status": "fail", "detail": "The source identifier is not recognized by Nova."}],
            "warnings": ["Do not enter personal information or proceed with this application."],
            "apply_url": None,
        }

    provider, slug = parsed_id
    expected_company = COMPANY_NAMES.get(slug, slug.replace("-", " ").replace("_", " ").title())
    official_domain = COMPANY_DOMAINS.get(slug)
    submitted = urlparse(submitted_url)
    # Greenhouse now serves some hosted job pages from job-boards.greenhouse.io,
    # while older listings and feeds may still use boards.greenhouse.io.
    # Match exact hostnames (never suffix/lookalike domains) and the board slug.
    ats_hosts = {"boards.greenhouse.io", "job-boards.greenhouse.io"} if provider == "greenhouse" else {"jobs.lever.co"}
    # Some employers use a custom careers domain as the Greenhouse-hosted
    # application URL. Trust that host only when it is the curated official
    # company domain, then require an exact match with the live ATS feed below.
    allowed_hosts = set(ats_hosts)
    submitted_host = (submitted.hostname or "").lower().rstrip(".")
    path_slug = (submitted.path.strip("/").split("/") or [""])[0]
    is_ats_host = submitted_host in ats_hosts
    is_official_company_host = bool(official_domain and _host_matches(submitted_host, official_domain))
    allowed_host = submitted_host
    if is_official_company_host:
        allowed_hosts.add(submitted_host)

    if (
        submitted.scheme.lower() != "https"
        or (not is_ats_host and not is_official_company_host)
        or (is_ats_host and path_slug.lower() != slug.lower())
    ):
        expected_hosts = " or ".join(sorted(allowed_hosts))
        return {
            "status": "High risk",
            "risk_level": "high",
            "summary": "The application URL does not match the employer board configured for this listing.",
            "checks": [{"name": "Application destination", "status": "fail", "detail": f"Expected an HTTPS URL on {expected_hosts} for board {slug}."}],
            "warnings": ["The URL supplied by the browser does not match Nova's source record. Do not proceed."],
            "apply_url": None,
        }

    def _canonical_job_url(value: str) -> tuple[str, str, str]:
        parsed = urlparse(value)
        return (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower().rstrip("."),
            parsed.path.rstrip("/"),
        )

    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"Accept": "application/json", "User-Agent": "NovaJobVerification/1.0"}) as client:
        try:
            published = await _load_published_job(client, provider, slug, parsed_id[1] and job_id.split(":", 2)[2])
        except (httpx.HTTPError, ValueError, KeyError):
            published = None

        if not published:
            return {
                "status": "Needs review",
                "risk_level": "medium",
                "summary": "Nova could not confirm that this exact role is still present in the employer's live public job feed.",
                "checks": [{"name": "Published listing", "status": "review", "detail": "The employer board could not confirm this job ID. It may have expired or the provider may be temporarily unavailable."}],
                "warnings": ["Do not apply until you confirm the role on the company's official careers page."],
                "apply_url": None,
            }

        live_title = published.get("title") if provider == "greenhouse" else published.get("text")
        live_url = published.get("absolute_url") if provider == "greenhouse" else (published.get("hostedUrl") or published.get("applyUrl"))
        live_url = live_url or ""
        live_company = expected_company

        if _canonical_job_url(live_url) != _canonical_job_url(submitted_url) or (live_title or "").strip().casefold() != submitted_title.strip().casefold() or live_company.strip().casefold() != submitted_company.strip().casefold():
            return {
                "status": "High risk",
                "risk_level": "high",
                "summary": "The job details supplied by the page do not match the employer's live listing.",
                "checks": [{"name": "Listing consistency", "status": "fail", "detail": "The title, company, or application URL differs from the live employer feed."}],
                "warnings": ["Do not proceed. Refresh the job search and verify the listing again."],
                "apply_url": None,
            }

        checks = [
            {"name": "Live employer listing", "status": "pass", "detail": f"The exact job ID, title, and application URL were confirmed in {provider.title()}'s live public feed for {expected_company}."},
            {"name": "Application destination", "status": "pass", "detail": f"The link uses HTTPS on the expected {allowed_host} employer board or curated company careers domain."},
        ]
        warnings = []
        if official_domain:
            domain_status, domain_detail = await _check_company_domain(client, official_domain)
            checks.append({"name": "Company website", "status": domain_status, "detail": domain_detail})
            if domain_status != "pass":
                warnings.append("Nova could not independently confirm the company's website during this check.")
        else:
            checks.append({"name": "Company website", "status": "review", "detail": "No curated official-domain record exists for this employer."})
            warnings.append("The company's official website has not been independently checked.")

        description = published.get("content") or published.get("descriptionPlain") or published.get("description") or ""
        description = re.sub(r"<[^>]+>", " ", str(description))
        for pattern, warning in SCAM_PATTERNS:
            if re.search(pattern, description, flags=re.IGNORECASE):
                warnings.append(warning)

        high_risk = any("fee" in item.lower() or "payment" in item.lower() or "money-transfer" in item.lower() for item in warnings)
        if high_risk:
            status, risk_level = "High risk", "high"
        elif warnings or any(item["status"] == "review" for item in checks):
            status, risk_level = "Needs review", "medium"
        else:
            status, risk_level = "Verified source", "low"

        return {
            "status": status,
            "risk_level": risk_level,
            "summary": "Nova confirmed the exact listing against the employer's live public job feed. This does not guarantee the recruiter or every communication is genuine.",
            "company": expected_company,
            "official_domain": official_domain,
            "checked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "checks": checks,
            "warnings": warnings or ["No obvious payment or messaging-only scam indicators were found in the published description. Recruiter identity is not verified by this check."],
            "apply_url": live_url if risk_level != "high" else None,
        }
