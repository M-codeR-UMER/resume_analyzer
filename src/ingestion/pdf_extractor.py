from __future__ import annotations

import logging
from io import BytesIO

try:
	import pdfplumber
except Exception:  # pragma: no cover - optional dependency fallback
	pdfplumber = None  # type: ignore[assignment]

try:
	from pdf2image import convert_from_bytes
except Exception:  # pragma: no cover - optional dependency fallback
	convert_from_bytes = None  # type: ignore[assignment]

try:
	import pytesseract
except Exception:  # pragma: no cover - optional dependency fallback
	pytesseract = None  # type: ignore[assignment]

from src.ingestion.parser_base import ResumeParser

logger = logging.getLogger(__name__)

_MIN_TEXT_LENGTH = 50


def _fallback_decode(file_bytes: bytes) -> str:
	for encoding in ("utf-8", "utf-16", "latin-1"):
		try:
			return file_bytes.decode(encoding)
		except UnicodeDecodeError:
			continue
	return ""


def _ocr_pdf(file_bytes: bytes) -> str:
	if convert_from_bytes is None or pytesseract is None:
		return ""
	try:
		images = convert_from_bytes(file_bytes)
		page_texts: list[str] = []
		for image in images:
			try:
				text = pytesseract.image_to_string(image)
				if text.strip():
					page_texts.append(text)
			except Exception:
				continue
		return "\n".join(page_texts)
	except Exception:
		return ""


class PDFResumeParser(ResumeParser):
	def parse(self, file_bytes: bytes, filename: str) -> str:
		text = ""
		if pdfplumber is not None:
			try:
				with pdfplumber.open(BytesIO(file_bytes)) as pdf:
					pages = [page.extract_text() or "" for page in pdf.pages]
				text = "\n".join(page for page in pages if page.strip())
			except Exception:
				text = ""

		if len(text.strip()) < _MIN_TEXT_LENGTH:
			ocr_text = _ocr_pdf(file_bytes)
			if ocr_text.strip():
				text = ocr_text

		if not text.strip():
			text = _fallback_decode(file_bytes)

		return text


def extract_pdf_text(file_bytes: bytes, filename: str) -> str:
	return PDFResumeParser().parse(file_bytes, filename)
