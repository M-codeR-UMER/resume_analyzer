import os
import sys
import uuid
import pytest

from fastapi.testclient import TestClient

# Ensure project root is on sys.path so `import src...` works when pytest is run
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.exceptions import BatchNotFoundError, JobNotFoundError
from src.main import app
from src.core.schemas import BatchUploadResponse, JobAnalyzeResponse, JobRequirement
from src.core.schemas import MatchResultsResponse, MatchRunResponse


@pytest.fixture()
def client():
    return TestClient(app)


def test_resumes_batch_upload_202_and_shape(client, monkeypatch):
    batch_id = uuid.uuid4()

    class StubPipeline:
        async def submit_resume_batch(self, files):
            # Ensure endpoint passes a list of UploadFile
            assert isinstance(files, list)
            return BatchUploadResponse(
                batch_id=batch_id,
                accepted_files=2,
                status="ACCEPTED",
            )

    import src.api.resumes as resumes_module

    monkeypatch.setattr(resumes_module, "get_pipeline", lambda: StubPipeline())

    # Minimal multipart payload: filename + bytes
    resp = client.post(
        "/resumes/batch-upload",
        files=[
            ("files", ("resume1.pdf", b"%PDF-1.4 test")),
            ("files", ("resume2.pdf", b"%PDF-1.4 test")),
        ],
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["batch_id"] == str(batch_id)
    assert body["accepted_files"] == 2
    assert body["status"] == "ACCEPTED"


def test_batch_status_404_shape(client, monkeypatch):
    missing_batch_id = uuid.uuid4()

    class StubPipeline:
        async def get_batch_status(self, batch_id):
            raise BatchNotFoundError(f"Batch not found: {batch_id}")

    import src.api.resumes as resumes_module

    monkeypatch.setattr(resumes_module, "get_pipeline", lambda: StubPipeline())

    resp = client.get(f"/resumes/batch/{missing_batch_id}/status")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert "Batch not found" in body["detail"]


def test_jobs_analyze_201_job_shape_and_fields(client, monkeypatch):
    job_id = uuid.uuid4()

    class StubPipeline:
        async def analyze_job(self, request):
            # Validate request fields arrive correctly
            assert request.title == "Python Backend Engineer"
            assert request.minimum_years_experience == 3

            job = JobRequirement(
                job_id=job_id,
                title=request.title,
                description=request.description,
                required_skills=["python", "fastapi", "sql"],
                preferred_skills=[],
                minimum_years_experience=request.minimum_years_experience,
                raw_text=request.description,
            )
            return JobAnalyzeResponse(job=job)

    import src.api.jobs as jobs_module

    monkeypatch.setattr(jobs_module, "get_pipeline", lambda: StubPipeline())

    resp = client.post(
        "/jobs/analyze",
        json={
            "title": "Python Backend Engineer",
            "description": "We need a Python backend engineer with FastAPI, SQL, and 3+ years of experience.",
            "minimum_years_experience": 3,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert "job" in body
    assert body["job"]["job_id"] == str(job_id)
    assert body["job"]["title"] == "Python Backend Engineer"
    assert body["job"]["minimum_years_experience"] == 3


def test_match_run_404_when_job_missing(client, monkeypatch):
    missing_job_id = uuid.uuid4()

    class StubPipeline:
        async def run_matching(self, job_id, batch_id=None):
            raise JobNotFoundError(f"Job not found: {job_id}")

    import src.api.matching as matching_module

    monkeypatch.setattr(matching_module, "get_pipeline", lambda: StubPipeline())

    resp = client.post(f"/match/run?job_id={missing_job_id}")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert "Job not found" in body["detail"]


def test_match_results_404_when_job_missing(client, monkeypatch):
    missing_job_id = uuid.uuid4()

    class StubPipeline:
        async def get_match_results(self, job_id):
            raise JobNotFoundError(f"Job not found: {job_id}")

    import src.api.matching as matching_module

    monkeypatch.setattr(matching_module, "get_pipeline", lambda: StubPipeline())

    resp = client.get(f"/match/results?job_id={missing_job_id}")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert "Job not found" in body["detail"]

