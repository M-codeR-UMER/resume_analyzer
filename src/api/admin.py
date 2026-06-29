from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.core.config import settings
from src.pipeline import get_pipeline

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset-candidates", status_code=status.HTTP_200_OK)
async def reset_candidates() -> dict[str, int]:
    if settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset endpoint only available in development environment",
        )
    pipeline = get_pipeline()
    count = await pipeline.repository.reset_candidates()
    pipeline.vector_store.reset_collection()
    return {"deleted": count}