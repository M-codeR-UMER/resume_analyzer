from __future__ import annotations

from src.core.config import settings
from src.core.schemas import Candidate, JobRequirement, MatchResult, ScoreBreakdown


def compute_experience_score(required_years: float, candidate_years: float) -> float:
	if required_years == 0:
		return 1.0
	if candidate_years >= required_years:
		return 1.0
	return max(0.0, candidate_years / required_years)


def build_explanation(matched: list[str], missing: list[str], required_exp: float, candidate_exp: float) -> str:
	total = len(matched) + len(missing)
	exp_note = (
		f"meets the {required_exp}-year experience requirement"
		if candidate_exp >= required_exp
		else f"has {candidate_exp} years vs the required {required_exp}"
	)
	return f"Matched {len(matched)}/{total} required skills and {exp_note}."


class ResumeScorer:
	def build_score(self, candidate: Candidate, job: JobRequirement, keyword_score: float, semantic_score: float) -> ScoreBreakdown:
		candidate_skills = {skill.lower() for skill in candidate.confirmed_skills}
		matched_skills = [skill for skill in job.required_skills if skill.lower() in candidate_skills]
		missing_skills = [skill for skill in job.required_skills if skill.lower() not in candidate_skills]
		experience_match_score = compute_experience_score(job.minimum_years_experience, candidate.years_experience)
		final_score = (
			settings.weight_keyword_score * keyword_score
			+ settings.weight_semantic_score * semantic_score
			+ settings.weight_experience_score * experience_match_score
		)
		explanation = build_explanation(matched_skills, missing_skills, job.minimum_years_experience, candidate.years_experience)
		return ScoreBreakdown(
			matched_skills=matched_skills,
			missing_skills=missing_skills,
			experience_match=f"{candidate.years_experience} yrs (required: {job.minimum_years_experience} yrs)",
			keyword_score=round(keyword_score, 4),
			semantic_similarity=round(semantic_score, 4),
			experience_match_score=round(experience_match_score, 4),
			final_score=round(final_score, 4),
			explanation=explanation,
		)

	def build_result(self, candidate: Candidate, job: JobRequirement, keyword_score: float, semantic_score: float, rank: int) -> MatchResult:
		return MatchResult(
			job_id=job.job_id,
			candidate_id=candidate.candidate_id,
			candidate_name=candidate.full_name or candidate.filename or str(candidate.candidate_id),
			rank=rank,
			score_breakdown=self.build_score(candidate, job, keyword_score, semantic_score),
		)
