import asyncio
import unittest
from unittest.mock import patch
import httpx

from backend.app.career_discovery import normalize_jsonld_jobs, _matches, _tavily_search
from backend.app.providers import _confirm_job_page


class CareerDiscoveryTests(unittest.TestCase):
    def test_extracts_schema_job_posting(self):
        document = """
        <html><script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Software Engineer",
          "url": "/jobs/123",
          "description": "Build reliable Java services.",
          "datePosted": "2026-11-01",
          "hiringOrganization": {"@type": "Organization", "name": "Example Corp"},
          "jobLocation": {"address": {
            "addressLocality": "Dallas",
            "addressRegion": "Texas",
            "addressCountry": "United States"
          }}
        }
        </script></html>
        """
        jobs = normalize_jsonld_jobs(
            document, "Example Corp", "https://careers.example.com/jobs"
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Software Engineer")
        self.assertEqual(jobs[0]["company"], "Example Corp")
        self.assertEqual(jobs[0]["url"], "https://careers.example.com/jobs/123")
        self.assertIn("Dallas", jobs[0]["location"])

    def test_ignores_non_https_job_urls(self):
        document = """
        <script type="application/ld+json">
        {"@type":"JobPosting","title":"Engineer","url":"http://example.com/job"}
        </script>
        """
        self.assertEqual(
            normalize_jsonld_jobs(document, "Example", "https://careers.example.com"),
            [],
        )

    def test_ignores_pages_without_job_posting_schema(self):
        document = """
        <script type="application/ld+json">
        {"@type":"Organization","name":"Example"}
        </script>
        """
        self.assertEqual(
            normalize_jsonld_jobs(document, "Example", "https://careers.example.com"),
            [],
        )

    def test_matches_india_location(self):
        job = {"title": "Software Engineer", "description": "Build Java services",
               "company": "Example", "location": "Hyderabad, Telangana, India"}
        self.assertTrue(_matches(job, "Software Engineer", "India"))
        self.assertFalse(_matches(job, "Software Engineer", "United States"))

    def test_tavily_results_are_restricted_to_career_and_ats_hosts(self):
        payload = {"results": [
            {"title": "Software Engineer", "url": "https://boards.greenhouse.io/example/jobs/123",
             "content": "Build Java services for Example Corp."},
            {"title": "Software Engineer", "url": "https://untrusted.example/blog/job",
             "content": "Build Java services."},
        ]}
        def handler(request):
            return httpx.Response(200, json=payload)
        async def run():
            with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    return await _tavily_search(client, "Software Engineer", "India", 20)
        jobs, status = asyncio.run(run())
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source"], "Company Career Site")
        self.assertEqual(status["provider"], "Tavily Career Search")

    def test_trusted_job_link_survives_automated_forbidden_response(self):
        def handler(request):
            return httpx.Response(403, request=request)
        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await _confirm_job_page(client, {
                    "url": "https://boards.greenhouse.io/example/jobs/123",
                    "source": "Greenhouse",
                })
        self.assertTrue(asyncio.run(run()))


if __name__ == "__main__":
    unittest.main()
