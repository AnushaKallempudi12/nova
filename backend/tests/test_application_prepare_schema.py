import unittest
from pydantic import ValidationError

# Import the FastAPI entry point first so its account router and SQLAlchemy models
# are initialized in the same order as the production ASGI application.
from backend.app.main import app  # noqa: F401
from backend.app.auth_api import ApplicationPrepareInput


class ApplicationPrepareSchemaTests(unittest.TestCase):
    def test_accepts_verified_https_destinations(self):
        payload = ApplicationPrepareInput(
            job_id="job-123",
            company="Example Corp",
            role="Software Engineer",
            job_url="https://careers.example.com/jobs/123",
            application_url="https://apply.example.com/jobs/123",
        )
        self.assertEqual(payload.company, "Example Corp")
        self.assertEqual(payload.application_url, "https://apply.example.com/jobs/123")

    def test_rejects_non_https_job_destination(self):
        with self.assertRaises(ValidationError):
            ApplicationPrepareInput(
                job_id="job-123",
                company="Example Corp",
                role="Software Engineer",
                job_url="http://careers.example.com/jobs/123",
            )

    def test_rejects_non_https_application_destination(self):
        with self.assertRaises(ValidationError):
            ApplicationPrepareInput(
                job_id="job-123",
                company="Example Corp",
                role="Software Engineer",
                job_url="https://careers.example.com/jobs/123",
                application_url="http://apply.example.com/jobs/123",
            )


if __name__ == "__main__":
    unittest.main()
