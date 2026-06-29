from __future__ import annotations

import re

from src.core.schemas import JobRequirement
from src.extraction.rule_base import COMMON_SKILLS


class JobDescriptionAnalyzer:
	def analyze(self, title: str, description: str, minimum_years_experience: float = 0.0) -> JobRequirement:
		lowered = description.lower()
		skills = sorted({skill for skill in COMMON_SKILLS if skill in lowered})
		years_match = re.search(r"(\d+(?:\.\d+)?)\+?\s+years?", description, re.IGNORECASE)
		required_years = float(years_match.group(1)) if years_match else minimum_years_experience
		return JobRequirement(
			title=title,
			description=description,
			required_skills=skills,
			preferred_skills=[],
			minimum_years_experience=required_years,
			raw_text=description,
		)
