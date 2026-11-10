import unittest

from backend.app.career_discovery import normalize_jsonld_jobs


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


if __name__ == "__main__":
    unittest.main()
