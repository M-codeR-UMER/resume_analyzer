from __future__ import annotations

from src.core.schemas import Candidate, JobRequirement


class KeywordMatcher:
	def score(self, candidate: Candidate, job: JobRequirement) -> float:
		required = [skill.lower() for skill in job.required_skills]
		if not required:
			return 0.0
		confirmed = {skill.lower() for skill in candidate.confirmed_skills}
		matched = sum(1 for skill in required if skill in confirmed)
		return matched / len(required)
