from src.api.admin import router as admin_router
from src.api.jobs import router as jobs_router
from src.api.matching import router as matching_router
from src.api.resumes import router as resumes_router

__all__ = ["admin_router", "jobs_router", "matching_router", "resumes_router"]