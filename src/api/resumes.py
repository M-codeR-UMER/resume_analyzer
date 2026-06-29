from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.core.exceptions import BatchNotFoundError
from src.pipeline import get_pipeline

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/batch-upload", status_code=status.HTTP_202_ACCEPTED)
async def batch_upload(files: list[UploadFile] = File(...)):
    pipeline = get_pipeline()
    return await pipeline.submit_resume_batch(files)


@router.get("/batch/{batch_id}/status")
async def batch_status(batch_id: UUID):
    pipeline = get_pipeline()
    try:
        return await pipeline.get_batch_status(batch_id)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: UUID):
    pipeline = get_pipeline()
    candidate = await pipeline.repository.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate.model_dump(mode="json")