import uuid

import os
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so `import src...` works when pytest is run
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.exceptions import BatchNotFoundError, JobNotFoundError
from src.main import app
from src.core.schemas import (

    BatchUploadResponse,
    CandidateStatus,
    JobAnalyzeResponse,
    JobRequirement,
    MatchResultsResponse,
    MatchRunResponse,
    MatchResult,
    MatchStatus,
    ResumeBatchStatus,
    ResumeBatchItem,
    ScoreBreakdown,
)


@pytest.fixture()
def client():
    return TestClient(app)


def _job_req(job_id: uuid.UUID) -> JobRequirement:
    return JobRequirement(
        job_id=job_id,
        title="Python Backend Engineer",
        description="We need a Python backend engineer with FastAPI, SQL.",
        required_skills=["python", "fastapi", "sql"],
        preferred_skills=[],
        minimum_years_experience=3,
        raw_text="raw",
    )


def test_health_ok(client, monkeypatch):
    # No need to patch pipeline for /health
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_jobs_analyze_happy_path(client, monkeypatch):
    job_id = uuid.uuid4()

    class StubPipeline:
        async def analyze_job(self, request):
            return JobAnalyzeResponse(job=_job_req(job_id))

    # Patch the imported get_pipeline inside the router module
    import src.api.jobs as jobs_module

    async def _get_pipeline_stub():
        return StubPipeline()

    # get_pipeline is sync in our code, so keep it sync
    monkeypatch.setattr(jobs_module, "get_pipeline", lambda: StubPipeline())

    resp = client.post(
        "/jobs/analyze",
        json={
            "title": "Python Backend Engineer",
            "description": "We need a Python backend engineer with FastAPI, SQL.",
            "minimum_years_experience": 3,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["job"]["job_id"] == str(job_id)
    assert body["job"]["minimum_years_experience"] == 3


def test_match_run_happy_path(client, monkeypatch):
    job_id = uuid.uuid4()

    class StubPipeline:
        async def run_matching(self, requested_job_id, batch_id=None):
            assert str(requested_job_id) == str(job_id)
            return MatchRunResponse(job_id=job_id, status="DONE", matched_candidates=12)

    import src.api.matching as matching_module

    monkeypatch.setattr(matching_module, "get_pipeline", lambda: StubPipeline())

    resp = client.post(f"/match/run?job_id={job_id}")
    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"] == str(job_id)
    assert body["status"] == "DONE"
    assert body["matched_candidates"] == 12


def test_match_results_happy_path(client, monkeypatch):
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    result_id = uuid.uuid4()
    score = ScoreBreakdown(
        matched_skills=["python", "fastapi"],
        missing_skills=["redis"],
        experience_match="exceeds",
        keyword_score=0.82,
        semantic_similarity=0.76,
        experience_match_score=1.0,
        final_score=0.79,
        explanation="Matched skills",
    )

    match_result = MatchResult(
        result_id=result_id,
        job_id=job_id,
        candidate_id=candidate_id,
        candidate_name="Jane Doe",
        rank=1,
        status=MatchStatus.DONE,
        score_breakdown=score,
    )

    class StubPipeline:
        async def get_match_results(self, requested_job_id):
            assert str(requested_job_id) == str(job_id)
            return MatchResultsResponse(job_id=job_id, results=[match_result])

    import src.api.matching as matching_module

    monkeypatch.setattr(matching_module, "get_pipeline", lambda: StubPipeline())

    resp = client.get(f"/match/results?job_id={job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == str(job_id)
    assert body["results"][0]["result_id"] == str(result_id)
    assert body["results"][0]["rank"] == 1
    assert body["results"][0]["score_breakdown"]["final_score"] == 0.79


def test_batch_status_returns_404_when_missing(client, monkeypatch):
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


def test_match_run_422_on_invalid_uuid(client):
    resp = client.post("/match/run?job_id=not-a-uuid")
    assert resp.status_code == 422


def test_jobs_analyze_422_when_description_missing(client):
    resp = client.post(
        "/jobs/analyze",
        json={
            "title": "Python Backend Engineer",
            "minimum_years_experience": 3,
        },
    )
    assert resp.status_code == 422

