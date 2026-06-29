from __future__ import annotations

import json
import logging
from typing import cast
from uuid import uuid4

from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.config import settings
from src.core.schemas import Candidate, CandidateStatus, SkillEvidence

_client = AsyncGroq(api_key=settings.groq_api_key)

_SYSTEM_PROMPT = """You are a resume information extractor. Extract ONLY the fields
listed below from the resume text. Do NOT invent an ID, batch ID, or status — those
are not your job. Respond with JSON matching this exact shape and nothing else:

{
  "full_name": string,
  "email": string,
  "phone": string,
  "years_experience": number,
  "current_role": string,
  "summary": string,
  "education": [string, ...],
  "certifications": [string, ...],
  "work_experience": [string, ...],
  "projects": [string, ...],
  "strengths": [string, ...] (3-5 short items derived ONLY from what is present in the resume; no speculation),
  "weaknesses": [string, ...] (3-5 short items derived ONLY from what is absent or weak in the resume; no speculation),
  "skills": [string, ...],
  "skill_evidence": {"<skill name>": "<exact quote from resume backing this skill>", ...}
}

Every skill in "skills" must also have an entry in "skill_evidence" quoting the
resume text that justifies it. Do not include skills you cannot quote evidence for."""

logger = logging.getLogger("resume_analyzer.extraction")


class LLMExtractedFields(BaseModel):
    """Narrow schema for what the LLM is allowed to produce.
    Deliberately excludes candidate_id, batch_id, status — those are
    system-assigned, never LLM-assigned, to prevent exactly the
    hallucinated-ID failures we hit (MALBER001, BATCH2026, status='New')."""

    model_config = ConfigDict(extra="ignore")

    full_name: str = ""
    email: str = ""
    phone: str = ""
    years_experience: float = 0.0
    current_role: str = ""
    summary: str = ""
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    work_experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_evidence: dict[str, str] = Field(default_factory=dict)


def _is_skill_verified(skill: str, evidence_text: str, resume_text: str) -> bool:
    """Anti-hallucination check: the evidence quote must actually appear in the
    source resume (case-insensitive substring match). If the LLM invents a
    quote, this catches it."""
    if not evidence_text:
        return False
    return evidence_text.strip().lower() in resume_text.lower()


async def _call_groq(resume_text: str, retry_feedback: str | None = None) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": resume_text},
    ]
    if retry_feedback:
        messages.append(
            {
                "role": "user",
                "content": f"Your previous response was invalid: {retry_feedback}. "
                f"Return corrected JSON matching the required shape exactly.",
            }
        )
    response = await _client.chat.completions.create(
        model=settings.groq_model,
        messages=cast(list[ChatCompletionMessageParam], messages),
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response.choices[0].message.content or ""


class GroqCandidateExtractor:
    """Matches pipeline.py's usage: self.llm_extractor.extract(text, filename=file_name)"""

    async def extract(self, text: str, filename: str) -> Candidate:
        resume_text = text
        logger.info("[%s] input resume text length: %d chars", filename, len(text))
        raw_output = await _call_groq(resume_text)
        extracted: LLMExtractedFields | None = None
        needs_review_reason: str | None = None

        try:
            extracted = LLMExtractedFields.model_validate(json.loads(raw_output))
        except (json.JSONDecodeError, ValidationError) as exc:
            try:
                raw_output_retry = await _call_groq(resume_text, retry_feedback=str(exc))
                extracted = LLMExtractedFields.model_validate(json.loads(raw_output_retry))
            except (json.JSONDecodeError, ValidationError) as exc2:
                extracted = LLMExtractedFields()
                needs_review_reason = f"LLM extraction failed validation twice: {exc2}"

        confirmed_skills: list[str] = []
        unverified_skills: list[str] = []
        skill_evidence_list: list[SkillEvidence] = []

        for skill in extracted.skills:
            evidence_text = extracted.skill_evidence.get(skill, "")
            verified = _is_skill_verified(skill, evidence_text, resume_text)
            skill_evidence_list.append(
                SkillEvidence(skill=skill, verified=verified, source_text=evidence_text or None)
            )
            if verified:
                confirmed_skills.append(skill)
            else:
                unverified_skills.append(skill)

        if unverified_skills and needs_review_reason is None:
            needs_review_reason = f"Unverified skills (no matching evidence in resume text): {unverified_skills}"

        dedupe_key = ""
        if extracted.email:
            dedupe_key = f"email:{(extracted.email or '').strip().lower()}"
        else:
            dedupe_key = f"name:{(extracted.full_name or '').strip().lower()}|file:{filename}"
        candidate = Candidate(
            candidate_id=uuid4(),
            filename=filename,
            full_name=extracted.full_name,
            email=extracted.email,
            phone=extracted.phone,
            years_experience=extracted.years_experience,
            current_role=extracted.current_role,
            summary=extracted.summary,
            education=extracted.education,
            certifications=extracted.certifications,
            work_experience=extracted.work_experience,
            projects=extracted.projects,
            strengths=extracted.strengths,
            weaknesses=extracted.weaknesses,
            text=resume_text,
            confirmed_skills=confirmed_skills,
            unverified_skills=unverified_skills,
            skill_evidence=skill_evidence_list,
            status=CandidateStatus.NEEDS_REVIEW if needs_review_reason else CandidateStatus.DONE,
            needs_review_reason=needs_review_reason,
            dedupe_key=dedupe_key,
        )

        candidate_dict = candidate.model_dump(exclude={"text"})
        logger.info("=== Extracted candidate fields for %s ===", filename)
        for key, value in candidate_dict.items():
            logger.info("  %s: %r", key, value)
        logger.info("=== Raw LLM JSON output for %s ===\n%s", filename, raw_output)

        return candidate