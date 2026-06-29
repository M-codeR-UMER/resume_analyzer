from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.core.exceptions import JobNotFoundError
from src.pipeline import get_pipeline

router = APIRouter(prefix="/match", tags=["matching"])


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_matching(
    job_id: UUID = Query(...),
    batch_id: UUID | None = Query(None, description="Filter candidates by batch ID"),
):
    pipeline = get_pipeline()
    try:
        return await pipeline.run_matching(job_id, batch_id=batch_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/results")
async def get_results(job_id: UUID = Query(...)):
    pipeline = get_pipeline()
    try:
        return await pipeline.get_match_results(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc