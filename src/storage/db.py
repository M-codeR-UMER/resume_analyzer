from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiosqlite

from src.core.config import settings
from src.core.exceptions import BatchNotFoundError, JobNotFoundError

from src.core.schemas import (
	Candidate,
	CandidateStatus,
	JobRequirement,
	MatchResult,
	MatchStatus,
	ResumeBatchItem,
	ResumeBatchStatus,
	utc_now,
)


DB_PATH = Path(settings.database_url.replace("sqlite+aiosqlite:///", ""))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
	batch_id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batch_items (
	batch_id TEXT NOT NULL,
	file_name TEXT NOT NULL,
	candidate_id TEXT,
	status TEXT NOT NULL,
	error TEXT,
	PRIMARY KEY (batch_id, file_name)
);

CREATE TABLE IF NOT EXISTS candidates (
	candidate_id TEXT PRIMARY KEY,
	dedupe_key TEXT,
	data TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidates_dedupe_key ON candidates(dedupe_key);

CREATE TABLE IF NOT EXISTS jobs (
	job_id TEXT PRIMARY KEY,
	data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_results (
	result_id TEXT PRIMARY KEY,
	job_id TEXT NOT NULL,
	data TEXT NOT NULL,
	rowid_order INTEGER
);
"""


class SQLiteRepository:
	"""SQLite-backed replacement for the previous in-memory repository."""

	def __init__(self) -> None:
		self._lock = asyncio.Lock()
		self._initialized = False

	async def init_db(self) -> None:
		if self._initialized:
			return
		DB_PATH.parent.mkdir(parents=True, exist_ok=True)
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			await db.execute("PRAGMA journal_mode=WAL;")
			await db.executescript(_SCHEMA)
			await db.commit()
		self._initialized = True

	async def _ensure_init(self) -> None:
		await self.init_db()

	async def create_batch(self, file_names: list[str]) -> ResumeBatchStatus:
		await self._ensure_init()
		async with self._lock, aiosqlite.connect(DB_PATH.as_posix()) as db:
			unique_file_names = list(dict.fromkeys(file_names))
			batch_id = uuid4()
			created_at = utc_now()
			await db.execute(
				"INSERT INTO batches (batch_id, created_at) VALUES (?, ?)",
				(str(batch_id), created_at.isoformat()),
			)
			for file_name in unique_file_names:
				await db.execute(
					"INSERT INTO batch_items (batch_id, file_name, candidate_id, status, error) VALUES (?, ?, ?, ?, ?)",
					(str(batch_id), file_name, None, CandidateStatus.QUEUED.value, None),
				)
			await db.commit()
			return await self._fetch_batch_status(db, batch_id, created_at.isoformat())

	async def set_batch_item(
		self,
		batch_id: UUID,
		file_name: str,
		*,
		status: CandidateStatus,
		candidate_id: UUID | None = None,
		error: str | None = None,
	) -> ResumeBatchStatus:
		await self._ensure_init()
		async with self._lock, aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute("SELECT created_at FROM batches WHERE batch_id = ?", (str(batch_id),))
			row = await cursor.fetchone()
			if row is None:
				raise BatchNotFoundError(f"Batch {batch_id} was not found")
			created_at = row[0]
			await db.execute(
				"UPDATE batch_items SET status = ?, candidate_id = ?, error = ? WHERE batch_id = ? AND file_name = ?",
				(status.value, str(candidate_id) if candidate_id else None, error, str(batch_id), file_name),
			)
			await db.commit()
			return await self._fetch_batch_status(db, batch_id, created_at)

	async def save_candidate(self, candidate: Candidate) -> Candidate:
		await self._ensure_init()
		async with self._lock, aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute(
				"SELECT candidate_id FROM candidates WHERE dedupe_key = ?",
				(candidate.dedupe_key,),
			)
			row = await cursor.fetchone()
			if row is not None:
				existing_id = UUID(row[0])
				candidate.candidate_id = existing_id
			await db.execute(
				"INSERT OR REPLACE INTO candidates (candidate_id, dedupe_key, data) VALUES (?, ?, ?)",
				(str(candidate.candidate_id), candidate.dedupe_key, candidate.model_dump_json()),
			)
			await db.commit()
		return candidate

	def _compute_dedupe_key(self, candidate: Candidate) -> str:
		email = (candidate.email or "").strip().lower()
		if email:
			return f"email:{email}"
		name = (candidate.full_name or "").strip().lower()
		filename = (candidate.filename or "").strip().lower()
		return f"name:{name}|file:{filename}"

	async def reset_candidates(self) -> int:
		await self._ensure_init()
		async with self._lock, aiosqlite.connect(DB_PATH.as_posix()) as db:
			await db.execute("DELETE FROM candidates")
			await db.commit()
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute("SELECT COUNT(*) FROM candidates")
			row = await cursor.fetchone()
			return row[0] if row else 0

	async def list_candidates(self, batch_id: UUID | None = None) -> list[Candidate]:
		"""List all candidates, optionally filtered by batch_id."""
		await self._ensure_init()
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute("SELECT data FROM candidates")
			rows = await cursor.fetchall()
			all_candidates = [Candidate.model_validate_json(row[0]) for row in rows]
			if batch_id is not None:
				return [c for c in all_candidates if c.batch_id == batch_id]
			return all_candidates

	async def get_candidate(self, candidate_id: UUID) -> Candidate | None:
		await self._ensure_init()
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute("SELECT data FROM candidates WHERE candidate_id = ?", (str(candidate_id),))
			row = await cursor.fetchone()
			if row is None:
				return None
			return Candidate.model_validate_json(row[0])

	async def save_job(self, job: JobRequirement) -> JobRequirement:
		await self._ensure_init()
		async with self._lock, aiosqlite.connect(DB_PATH.as_posix()) as db:
			await db.execute(
				"INSERT OR REPLACE INTO jobs (job_id, data) VALUES (?, ?)",
				(str(job.job_id), job.model_dump_json()),
			)
			await db.commit()
			return job

	async def get_job(self, job_id: UUID) -> JobRequirement:
		await self._ensure_init()
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute("SELECT data FROM jobs WHERE job_id = ?", (str(job_id),))
			row = await cursor.fetchone()
			if row is None:
				raise JobNotFoundError(f"Job {job_id} was not found")
			return JobRequirement.model_validate_json(row[0])

	async def save_match_results(self, job_id: UUID, results: list[MatchResult]) -> list[MatchResult]:
		await self._ensure_init()
		async with self._lock, aiosqlite.connect(DB_PATH.as_posix()) as db:
			await db.execute("DELETE FROM match_results WHERE job_id = ?", (str(job_id),))
			for order, result in enumerate(results):
				result.status = MatchStatus.DONE
				await db.execute(
					"INSERT INTO match_results (result_id, job_id, data, rowid_order) VALUES (?, ?, ?, ?)",
					(str(result.result_id), str(job_id), result.model_dump_json(), order),
				)
			await db.commit()
			return results

	async def get_match_results(self, job_id: UUID) -> list[MatchResult]:
		await self._ensure_init()
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute(
				"SELECT data FROM match_results WHERE job_id = ? ORDER BY rowid_order ASC",
				(str(job_id),),
			)
			rows = await cursor.fetchall()
			return [MatchResult.model_validate_json(row[0]) for row in rows]

	async def get_batch_status(self, batch_id: UUID) -> ResumeBatchStatus:
		await self._ensure_init()
		async with aiosqlite.connect(DB_PATH.as_posix()) as db:
			cursor = await db.execute(
				"SELECT created_at FROM batches WHERE batch_id = ?",
				(str(batch_id),),
			)
			row = await cursor.fetchone()
			if row is None:
				raise BatchNotFoundError(f"Batch {batch_id} was not found")
			return await self._fetch_batch_status(db, batch_id, row[0])

	async def _fetch_batch_status(self, db: aiosqlite.Connection, batch_id: UUID, created_at: str) -> ResumeBatchStatus:
		cursor = await db.execute(
			"SELECT file_name, candidate_id, status, error FROM batch_items WHERE batch_id = ?",
			(str(batch_id),),
		)
		rows = await cursor.fetchall()
		items = [
			ResumeBatchItem(
				file_name=row[0],
				candidate_id=UUID(row[1]) if row[1] else None,
				status=CandidateStatus(row[2]),
				error=row[3],
			)
			for row in rows
		]
		done = sum(1 for item in items if item.status == CandidateStatus.DONE)
		needs_review = sum(1 for item in items if item.status == CandidateStatus.NEEDS_REVIEW)
		failed = sum(1 for item in items if item.status == CandidateStatus.FAILED)
		processed = done + needs_review + failed
		return ResumeBatchStatus(
			batch_id=batch_id,
			total_files=len(items),
			processed_files=processed,
			done_files=done,
			needs_review_files=needs_review,
			failed_files=failed,
			items=items,
			created_at=datetime.fromisoformat(created_at),
		)