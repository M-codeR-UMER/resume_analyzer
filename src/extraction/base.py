from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.schemas import Candidate


class InfoExtractor(ABC):
	@abstractmethod
	async def extract(self, text: str, filename: str | None = None) -> Candidate:
		raise NotImplementedError
