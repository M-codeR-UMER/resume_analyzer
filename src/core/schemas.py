from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


class CandidateStatus(str, Enum):
	QUEUED = "QUEUED"
	PROCESSING = "PROCESSING"
	DONE = "DONE"
	NEEDS_REVIEW = "NEEDS_REVIEW"
	FAILED = "FAILED"


class MatchStatus(str, Enum):
	QUEUED = "QUEUED"
	RUNNING = "RUNNING"
	DONE = "DONE"
	FAILED = "FAILED"


class SkillEvidence(BaseModel):
	model_config = ConfigDict(extra="forbid")

	skill: str
	verified: bool = True
	source_text: str | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID = Field(default_factory=uuid4)
    batch_id: UUID | None = None
    filename: str | None = None
    full_name: str = ""
    email: str = ""
    phone: str = ""
    years_experience: float = 0.0
    current_role: str = ""
    summary: str = ""
    text: str = ""
    confirmed_skills: list[str] = Field(default_factory=list)
    unverified_skills: list[str] = Field(default_factory=list)
    skill_evidence: list[SkillEvidence] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    work_experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.QUEUED
    needs_review_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    dedupe_key: str | None = None


class JobRequirement(BaseModel):
	model_config = ConfigDict(extra="forbid")

	job_id: UUID = Field(default_factory=uuid4)
	title: str = ""
	description: str = ""
	required_skills: list[str] = Field(default_factory=list)
	preferred_skills: list[str] = Field(default_factory=list)
	minimum_years_experience: float = 0.0
	raw_text: str = ""
	created_at: datetime = Field(default_factory=utc_now)


class ScoreBreakdown(BaseModel):
	model_config = ConfigDict(extra="forbid")

	matched_skills: list[str] = Field(default_factory=list)
	missing_skills: list[str] = Field(default_factory=list)
	experience_match: str = ""
	keyword_score: float = 0.0
	semantic_similarity: float = 0.0
	experience_match_score: float = 0.0
	final_score: float = 0.0
	explanation: str = ""


class MatchResult(BaseModel):
	model_config = ConfigDict(extra="forbid")

	result_id: UUID = Field(default_factory=uuid4)
	job_id: UUID
	candidate_id: UUID
	candidate_name: str
	rank: int = 0
	status: MatchStatus = MatchStatus.QUEUED
	score_breakdown: ScoreBreakdown
	created_at: datetime = Field(default_factory=utc_now)


class ResumeBatchItem(BaseModel):
	model_config = ConfigDict(extra="forbid")

	file_name: str
	candidate_id: UUID | None = None
	status: CandidateStatus = CandidateStatus.QUEUED
	error: str | None = None


class ResumeBatchStatus(BaseModel):
	model_config = ConfigDict(extra="forbid")

	batch_id: UUID
	total_files: int
	processed_files: int
	done_files: int
	needs_review_files: int
	failed_files: int
	items: list[ResumeBatchItem] = Field(default_factory=list)
	created_at: datetime = Field(default_factory=utc_now)


class BatchUploadResponse(BaseModel):
	model_config = ConfigDict(extra="forbid")

	batch_id: UUID
	accepted_files: int
	status: str


class JobAnalyzeRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	title: str
	description: str
	minimum_years_experience: float = 0.0


class JobAnalyzeResponse(BaseModel):
	model_config = ConfigDict(extra="forbid")

	job: JobRequirement


class MatchRunResponse(BaseModel):
	model_config = ConfigDict(extra="forbid")

	job_id: UUID
	status: str
	matched_candidates: int


class MatchResultsResponse(BaseModel):
	model_config = ConfigDict(extra="forbid")

	job_id: UUID
	results: list[MatchResult] = Field(default_factory=list)


class ErrorResponse(BaseModel):
	model_config = ConfigDict(extra="forbid")

	detail: str


class ResumeTextPayload(BaseModel):
	model_config = ConfigDict(extra="forbid")

	filename: str
	text: str
	batch_id: UUID | None = None
	metadata: dict[str, Any] = Field(default_factory=dict)
