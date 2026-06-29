from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from src.core.schemas import Candidate, SkillEvidence


EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}")

COMMON_SKILLS = {
	"python",
	"fastapi",
	"sql",
	"sqlite",
	"postgresql",
	"pandas",
	"numpy",
	"machine learning",
	"nlp",
	"docker",
	"aws",
	"azure",
	"javascript",
	"typescript",
	"react",
	"streamlit",
	"scikit-learn",
	"tensorflow",
	"pytorch",
}


def _first_nonempty_line(text: str) -> str:
	for line in text.splitlines():
		cleaned = line.strip()
		if cleaned:
			return cleaned
	return ""


def _candidate_name(text: str) -> str:
	first_line = _first_nonempty_line(text)
	if not first_line:
		return ""
	if len(first_line.split()) <= 5:
		return first_line
	return ""


def _find_verified_skills(text: str, skills: Iterable[str]) -> tuple[list[str], list[str], list[SkillEvidence]]:
	lowered = text.lower()
	confirmed: list[str] = []
	unverified: list[str] = []
	evidence: list[SkillEvidence] = []
	for skill in skills:
		normalized = skill.lower().strip()
		found = normalized in lowered or any(
			SequenceMatcher(None, normalized, token).ratio() >= 0.86
			for token in lowered.split()
		)
		if found:
			confirmed.append(skill)
			evidence.append(SkillEvidence(skill=skill, verified=True, source_text=skill))
		else:
			unverified.append(skill)
			evidence.append(SkillEvidence(skill=skill, verified=False, source_text=None))
	return confirmed, unverified, evidence


class RuleBasedExtractor:
	def extract(self, text: str, filename: str | None = None) -> Candidate:
		email_match = EMAIL_PATTERN.search(text)
		phone_match = PHONE_PATTERN.search(text)
		detected_skills = sorted({skill for skill in COMMON_SKILLS if skill in text.lower()})
		confirmed_skills, unverified_skills, evidence = _find_verified_skills(text, detected_skills)

		years_match = re.search(r"(\d+(?:\.\d+)?)\+?\s+years?", text, re.IGNORECASE)
		years_experience = float(years_match.group(1)) if years_match else 0.0

		return Candidate(
			filename=filename,
			full_name=_candidate_name(text),
			email=email_match.group(0) if email_match else "",
			phone=phone_match.group(0) if phone_match else "",
			years_experience=years_experience,
			text=text,
			confirmed_skills=confirmed_skills,
			unverified_skills=unverified_skills,
			skill_evidence=evidence,
		)
