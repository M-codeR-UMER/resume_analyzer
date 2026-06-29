from __future__ import annotations

from fastapi import APIRouter, status

from src.core.schemas import JobAnalyzeRequest
from src.pipeline import get_pipeline

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/analyze", status_code=status.HTTP_201_CREATED)
async def analyze_job(request: JobAnalyzeRequest):
    pipeline = get_pipeline()
    return await pipeline.analyze_job(request)