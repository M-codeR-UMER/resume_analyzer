# Build Prompt: AI-Powered Resume Screening & Candidate Ranking System

You are a senior backend/AI engineer. Build the following project end-to-end, following the exact architecture, tech stack, and engineering practices below. Do not deviate from the structure unless something is technically impossible — if so, flag it and explain why before substituting.

## Project Summary

Build "resume-analyzer": a system that ingests resumes (PDF), extracts structured candidate data via NLP + LLM, accepts a job description, matches/ranks candidates against it with an explainable scoring methodology, and exposes everything through a FastAPI backend with a Streamlit dashboard frontend.

## Tech Stack (fixed — do not substitute)

- Python 3.13, `uv` for dependency management
- FastAPI + Uvicorn (backend API)
- Streamlit (dashboard frontend, calls backend via `httpx`)
- pdfplumber (PDF text extraction)
- spaCy (`en_core_web_sm`) for rule-based NER (names, orgs)
- Groq API (`groq` SDK, OpenAI-compatible) for structured LLM extraction — use Llama 3.3 70B (`llama-3.3-70b-versatile`) for extraction quality, with JSON mode / response_format schema enforcement — not free-text prompting
- sentence-transformers (`all-MiniLM-L6-v2`) for semantic embeddings — chosen for CPU-only, low-RAM deployment
- scikit-learn for TF-IDF keyword matching
- ChromaDB (persistent disk mode, not in-memory) for vector search
- SQLite (via `aiosqlite`) for structured storage, WAL mode enabled
- Pydantic v2 for all schemas and validation gates
- Celery + Redis for background batch processing (if unavailable in environment, fall back to FastAPI `BackgroundTasks` + an `asyncio.Semaphore` cap, and explicitly comment in code that this is an MVP substitute for a real worker queue)
- pytest, ruff, pre-commit for quality

## Folder Structure (build exactly this, with `__init__.py` in every package folder under `src/` except `ui/`)

```
resume-analyzer/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app instance + router registration ONLY
│   ├── pipeline.py              # orchestration layer — chains modules together
│   ├── core/
│   │   ├── schemas.py           # Candidate, JobRequirement, ScoreBreakdown, MatchResult
│   │   ├── config.py            # pydantic-settings, env vars
│   │   └── exceptions.py
│   ├── api/
│   │   ├── resumes.py           # APIRouter: upload, batch-upload, status
│   │   ├── jobs.py              # APIRouter: submit JD, analyze
│   │   └── matching.py          # APIRouter: run matching, get rankings
│   ├── ingestion/
│   │   ├── parser_base.py       # abstract ResumeParser
│   │   └── pdf_extractor.py
│   ├── extraction/
│   │   ├── base.py               # abstract InfoExtractor
│   │   ├── rule_based.py         # regex + spaCy: email, phone, names
│   │   └── llm_extractor.py      # Groq structured extraction + retry-on-validation-failure
│   ├── jobspec/
│   │   └── jd_analyzer.py
│   ├── matching/
│   │   ├── base.py               # abstract MatchingEngine
│   │   ├── keyword_matcher.py    # TF-IDF overlap
│   │   └── semantic_matcher.py   # sentence-transformers cosine similarity
│   ├── ranking/
│   │   └── scorer.py             # combines sub-scores, builds ScoreBreakdown + explanation text
│   ├── storage/
│   │   ├── db.py                 # SQLite (aiosqlite) CRUD
│   │   └── vector_store.py       # ChromaDB wrapper
│   └── ui/
│       └── app.py                # Streamlit dashboard, talks to FastAPI via httpx
├── workers/
│   └── tasks.py                  # Celery tasks: extract, embed, match (or asyncio fallback)
├── data/
│   ├── sample_resumes/
│   └── sample_jds/
├── tests/
├── docs/
│   └── scoring_methodology.md
├── pyproject.toml
└── README.md
```

## User Flow (implement exactly this request/response sequence)

1. Recruiter uploads N resumes (PDF) via Streamlit → `POST /resumes/batch-upload`
2. Endpoint returns `202 Accepted` + `batch_id` immediately; does NOT process inline
3. Each resume is queued as a background task: `extract_text → rule_based extraction → llm_extractor (validated) → save Candidate to SQLite → embed text → save vector to ChromaDB`
4. Streamlit polls `GET /resumes/batch/{batch_id}/status` until all resumes are `DONE` or `NEEDS_REVIEW`
5. Recruiter submits job description → `POST /jobs/analyze` → `jd_analyzer` extracts required skills/experience → stored as `JobRequirement`
6. Recruiter triggers ranking → `POST /match/run?job_id=...` → for each candidate: `keyword_matcher` + `semantic_matcher` scores → `scorer.py` combines into `ScoreBreakdown` with human-readable `explanation` → saved as `MatchResult`
7. Streamlit fetches `GET /match/results?job_id=...` → renders ranked table + per-candidate score breakdown + compare view + CSV export

## Engineering Requirements (non-negotiable — implement, don't skip)

### Concurrency
- Upload endpoints must return instantly; all CPU/LLM-heavy work happens in background tasks/workers, never inline in the request handler.
- CPU-bound steps (PDF parsing, embedding generation) must run in a process pool, not bare `async def`.
- LLM calls must use the `groq` SDK's async client so multiple resumes' extraction calls run concurrently.
- Cap concurrency explicitly (e.g. semaphore of 5) so 250 resumes don't open 250 simultaneous LLM connections.

### LLM Output Validation (anti-hallucination)
- Use Groq's JSON mode (`response_format={"type": "json_object"}`) with an explicit schema described in the system prompt, not loose free-text JSON prompting.
- Every LLM response must be parsed into the `Candidate` Pydantic model inside a `try/except ValidationError`. On failure, retry once with the validation error fed back into the prompt. On second failure, mark the record `NEEDS_REVIEW` — never insert invalid/partial data silently.
- Every extracted skill must be cross-checked against literal substring/fuzzy presence in the source resume text. Skills not found verbatim or near-verbatim are stored as `unverified_skill`, excluded from scoring, and flagged in the UI — only `confirmed_skill` entries count toward matching.

### Explainability
- `ScoreBreakdown` must never expose a raw cosine similarity number as the primary output. It must contain: `matched_skills`, `missing_skills`, `experience_match` (text), `keyword_score`, `semantic_similarity` (shown only as supporting detail), `final_score`, and a templated `explanation` string built from the counted overlaps (e.g. "Candidate matched 8/10 required skills and exceeds required experience by 1 year").
- Document the exact scoring formula in `docs/scoring_methodology.md`: `final_score = 0.4*keyword_score + 0.4*semantic_similarity + 0.2*experience_match_score`.

### Hardware/Cost Constraints
- Embeddings must be generated in batches (`model.encode(list, batch_size=16)`), never one-by-one in a loop.
- ChromaDB must run in persistent (disk-backed) mode, not in-memory.
- SQLite must use WAL mode for concurrent read safety.
- No GPU-dependent code paths; all inference must run correctly on CPU-only environments.

### Code Quality
- Every module folder (`ingestion`, `extraction`, `matching`) defines an abstract base class (`parser_base.py`, `base.py`) so implementations are swappable.
- `pipeline.py` contains all orchestration logic — API route files in `src/api/` must stay thin (parse request → call pipeline function → return response), no business logic inside route handlers.
- Type hints everywhere, Pydantic models for all data crossing module boundaries, ruff-clean, pytest coverage for extraction validation logic and scorer logic at minimum.

## Deliverable Order

1. `core/schemas.py` + `core/config.py`
2. `ingestion/` + `extraction/` (with validation/retry logic)
3. `storage/db.py` + `storage/vector_store.py`
4. `jobspec/jd_analyzer.py`
5. `matching/` + `ranking/scorer.py`
6. `pipeline.py` wiring all of the above
7. `api/` routers + `main.py`
8. `workers/tasks.py` for background processing
9. `ui/app.py` Streamlit dashboard
10. `docs/scoring_methodology.md` + `README.md`

Build in this order, and after each numbered step, pause and show the code before proceeding to the next.
