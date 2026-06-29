from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile

from src.core.config import settings
from src.core.schemas import BatchUploadResponse, CandidateStatus, JobAnalyzeRequest, JobAnalyzeResponse, MatchResultsResponse, MatchRunResponse, ResumeBatchStatus
from src.extraction.llm_extractor import GroqCandidateExtractor
from src.extraction.rule_base import RuleBasedExtractor
from src.ingestion.pdf_extractor import extract_pdf_text
from src.jobspec.jd_analyzer import JobDescriptionAnalyzer
from src.matching.keyword_matcher import KeywordMatcher
from src.matching.semantic_matcher import SemanticMatcher
from src.ranking.scorer import ResumeScorer
from src.storage.db import SQLiteRepository
from src.storage.vector_store import ChromaVectorStore


logger = logging.getLogger(__name__)


@dataclass
class ResumeAnalyzerPipeline:
    repository: SQLiteRepository
    vector_store: ChromaVectorStore
    job_analyzer: JobDescriptionAnalyzer
    rule_extractor: RuleBasedExtractor
    llm_extractor: GroqCandidateExtractor
    keyword_matcher: KeywordMatcher
    semantic_matcher: SemanticMatcher
    scorer: ResumeScorer

    def __init__(self) -> None:
        self.repository = SQLiteRepository()
        self.vector_store = ChromaVectorStore()
        self.job_analyzer = JobDescriptionAnalyzer()
        self.rule_extractor = RuleBasedExtractor()
        self.llm_extractor = GroqCandidateExtractor()
        self.keyword_matcher = KeywordMatcher()
        self.semantic_matcher = SemanticMatcher(model_name=settings.embedding_model)
        self.scorer = ResumeScorer()
        self._processing_tasks: set[asyncio.Task[None]] = set()
        self._llm_semaphore = asyncio.Semaphore(settings.max_concurrent_llm_calls)
        self._process_pool: ProcessPoolExecutor | None = None

    async def shutdown(self) -> None:
        if self._process_pool is not None:
            self._process_pool.shutdown(wait=False, cancel_futures=True)

    def _get_process_pool(self) -> ProcessPoolExecutor:
        if self._process_pool is None:
            self._process_pool = ProcessPoolExecutor(max_workers=2)
        return self._process_pool

    async def submit_resume_batch(self, files: list[UploadFile]) -> BatchUploadResponse:
        file_payloads = [(file.filename or f"resume-{index}.pdf", await file.read()) for index, file in enumerate(files, start=1)]
        batch_status = await self.repository.create_batch([file_name for file_name, _ in file_payloads])
        for file_name, file_bytes in file_payloads:
            task = asyncio.create_task(self._process_resume(batch_status.batch_id, file_name, file_bytes))
            self._processing_tasks.add(task)
            task.add_done_callback(self._processing_tasks.discard)
        return BatchUploadResponse(batch_id=batch_status.batch_id, accepted_files=len(file_payloads), status="ACCEPTED")

    async def _process_resume(self, batch_id: UUID, file_name: str, file_bytes: bytes) -> None:
        try:
            await self.repository.set_batch_item(batch_id, file_name, status=CandidateStatus.PROCESSING)
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(self._get_process_pool(), extract_pdf_text, file_bytes, file_name)
            if not text.strip():
                raise ValueError("No text could be extracted from the uploaded resume")
            _ = self.rule_extractor.extract(text, filename=file_name)
            async with self._llm_semaphore:
                candidate = await self.llm_extractor.extract(text, filename=file_name)
            candidate.batch_id = batch_id
            candidate.filename = file_name
            candidate.text = text
            candidate.dedupe_key = self.repository._compute_dedupe_key(candidate)
            candidate = await self.repository.save_candidate(candidate)
            self.vector_store.save_embedding(candidate.candidate_id, text)
            await self.repository.set_batch_item(batch_id, file_name, status=candidate.status, candidate_id=candidate.candidate_id, error=candidate.needs_review_reason)
        except Exception as exc:
            await self.repository.set_batch_item(batch_id, file_name, status=CandidateStatus.NEEDS_REVIEW, error=str(exc))

    async def get_batch_status(self, batch_id: UUID) -> ResumeBatchStatus:
        return await self.repository.get_batch_status(batch_id)

    async def analyze_job(self, request: JobAnalyzeRequest) -> JobAnalyzeResponse:
        job = self.job_analyzer.analyze(request.title, request.description, request.minimum_years_experience)
        saved_job = await self.repository.save_job(job)
        return JobAnalyzeResponse(job=saved_job)

    async def run_matching(self, job_id: UUID, batch_id: UUID | None = None) -> MatchRunResponse:
        job = await self.repository.get_job(job_id)
        candidates = await self.repository.list_candidates(batch_id=batch_id)
        scored_results = []
        for candidate in candidates:
            keyword_score = self.keyword_matcher.score(candidate, job)
            semantic_score = self.semantic_matcher.score(candidate, job)
            scored_results.append(self.scorer.build_result(candidate, job, keyword_score, semantic_score, rank=0))
        scored_results.sort(key=lambda result: result.score_breakdown.final_score, reverse=True)
        ranked_results = [result.model_copy(update={"rank": index}) for index, result in enumerate(scored_results, start=1)]
        await self.repository.save_match_results(job_id, ranked_results)
        return MatchRunResponse(job_id=job_id, status="DONE", matched_candidates=len(ranked_results))

    async def get_match_results(self, job_id: UUID) -> MatchResultsResponse:
        _ = await self.repository.get_job(job_id)
        results = await self.repository.get_match_results(job_id)
        return MatchResultsResponse(job_id=job_id, results=results)


_pipeline: ResumeAnalyzerPipeline | None = None


def get_pipeline() -> ResumeAnalyzerPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ResumeAnalyzerPipeline()
    return _pipeline