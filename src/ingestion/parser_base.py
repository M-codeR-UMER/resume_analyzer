from __future__ import annotations

from abc import ABC, abstractmethod


class ResumeParser(ABC):
	@abstractmethod
	def parse(self, file_bytes: bytes, filename: str) -> str:
		raise NotImplementedError
