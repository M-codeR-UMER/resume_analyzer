class ResumeAnalyzerError(Exception):
	"""Base exception for the application."""


class BatchNotFoundError(ResumeAnalyzerError):
	"""Raised when a batch id cannot be resolved."""


class JobNotFoundError(ResumeAnalyzerError):
	"""Raised when a job id cannot be resolved."""


class CandidateNotFoundError(ResumeAnalyzerError):
	"""Raised when a candidate id cannot be resolved."""


class ValidationReviewRequiredError(ResumeAnalyzerError):
	"""Raised when extracted data should be flagged for manual review."""
