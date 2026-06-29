from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.schemas import Candidate, JobRequirement, MatchResult


class MatchingEngine(ABC):
	@abstractmethod
	def score(self, candidate: Candidate, job: JobRequirement) -> MatchResult:
		raise NotImplementedError
