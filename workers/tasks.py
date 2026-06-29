from __future__ import annotations

import asyncio

from celery import Celery

from src.core.config import settings
from src.pipeline import get_pipeline


celery_app = Celery("resume_analyzer", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="resume_analyzer.process_resume_batch")
def process_resume_batch(batch_id: str, file_names: list[str]) -> dict[str, str]:
	# MVP fallback: Celery is scaffolded, but the active implementation still uses asyncio + semaphore in the pipeline.
	return {"batch_id": batch_id, "status": "QUEUED", "files": str(len(file_names))}


@celery_app.task(name="resume_analyzer.run_matching")
def run_matching(job_id: str) -> dict[str, str]:
	return {"job_id": job_id, "status": "QUEUED"}


async def submit_resume_batch(file_names: list[str]) -> str:
	pipeline = get_pipeline()
	batch = await pipeline.repository.create_batch(file_names)
	return str(batch.batch_id)


def submit_resume_batch_sync(file_names: list[str]) -> str:
	return asyncio.run(submit_resume_batch(file_names))