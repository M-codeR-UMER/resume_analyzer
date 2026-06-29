from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import admin_router, jobs_router, matching_router, resumes_router
from src.pipeline import get_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("resume_analyzer.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
	_ = get_pipeline()
	yield
	await get_pipeline().shutdown()


app = FastAPI(title="resume-analyzer", version="0.1.0", lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(matching_router)
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok"}