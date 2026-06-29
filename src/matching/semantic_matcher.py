from __future__ import annotations

from importlib import import_module
from typing import Any

try:
	SentenceTransformer: Any = getattr(import_module("sentence_transformers"), "SentenceTransformer")
except Exception:  # pragma: no cover - optional dependency fallback
	SentenceTransformer = None

from src.core.schemas import Candidate, JobRequirement


class SemanticMatcher:
	def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
		self._model_name = model_name
		self._model: Any = None

	def _ensure_model(self):
		if self._model is None and SentenceTransformer is not None:
			try:
				self._model = SentenceTransformer(self._model_name)
			except Exception:
				self._model = None
		return self._model

	def score(self, candidate: Candidate, job: JobRequirement) -> float:
		model = self._ensure_model()
		if model is None:
			candidate_terms = set(candidate.text.lower().split())
			job_terms = set(job.description.lower().split())
			union = candidate_terms | job_terms
			if not union:
				return 0.0
			return len(candidate_terms & job_terms) / len(union)

		embeddings = model.encode([candidate.text, job.description], batch_size=16, normalize_embeddings=True)
		candidate_vector, job_vector = embeddings
		return float(candidate_vector @ job_vector)
