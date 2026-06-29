# Database Design

## Overview

The Resume Analyzer system uses two database systems for different purposes:

- **SQLite** - Structured storage for candidates, job descriptions, match results, and batch metadata
- **ChromaDB** - Vector embeddings for semantic similarity search and candidate-job matching

---

## SQLite Database Design

### Table Schemas

#### Candidates Table

Stores extracted candidate information from resumes.

```sql
CREATE TABLE candidates (
    candidate_id TEXT PRIMARY KEY,
    batch_id TEXT,
    filename TEXT,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    years_experience REAL DEFAULT 0.0,
    current_role TEXT,
    summary TEXT,
    text TEXT,
    confirmed_skills TEXT,       -- JSON array
    unverified_skills TEXT,      -- JSON array
    skill_evidence TEXT,         -- JSON array
    status TEXT DEFAULT 'QUEUED',
    needs_review_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `candidate_id` | UUID | Unique identifier for each candidate |
| `batch_id` | UUID | Links candidate to their upload batch |
| `filename` | String | Original PDF filename |
| `full_name` | String | Extracted candidate name |
| `email` | String | Extracted email address |
| `phone` | String | Extracted phone number |
| `years_experience` | Float | Total years of experience |
| `current_role` | String | Current job title/role |
| `summary` | String | Professional summary |
| `text` | Text | Full extracted resume text |
| `confirmed_skills` | JSON | Skills verified in resume text |
| `unverified_skills` | JSON | Skills claimed but not found |
| `skill_evidence` | JSON | Source text for each skill |
| `status` | Enum | QUEUED, PROCESSING, DONE, NEEDS_REVIEW, FAILED |
| `needs_review_reason` | String | Error message if manual review needed |

---

#### Jobs Table

Stores structured job requirements extracted from job descriptions.

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    required_skills TEXT,        -- JSON array
    preferred_skills TEXT,       -- JSON array
    minimum_years_experience REAL DEFAULT 0.0,
    raw_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `job_id` | UUID | Unique identifier for each job |
| `title` | String | Job title |
| `description` | Text | Full job description |
| `required_skills` | JSON | Skills extracted from description |
| `preferred_skills` | JSON | Preferred (nice-to-have) skills |
| `minimum_years_experience` | Float | Minimum required experience |
| `raw_text` | Text | Original description text |

---

#### Match Results Table

Stores match results and scoring breakdown for each candidate-job pair.

```sql
CREATE TABLE match_results (
    result_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    rank INTEGER,
    status TEXT DEFAULT 'QUEUED',
    matched_skills TEXT,          -- JSON array
    missing_skills TEXT,          -- JSON array
    experience_match TEXT,
    keyword_score REAL DEFAULT 0.0,
    semantic_similarity REAL DEFAULT 0.0,
    experience_match_score REAL DEFAULT 0.0,
    final_score REAL DEFAULT 0.0,
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
);
```

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `result_id` | UUID | Unique identifier for this match result |
| `job_id` | UUID | Foreign key to jobs table |
| `candidate_id` | UUID | Foreign key to candidates table |
| `candidate_name` | String | Denormalized for quick display |
| `rank` | Integer | Ranking position for this job |
| `status` | Enum | QUEUED, RUNNING, DONE, FAILED |
| `matched_skills` | JSON | Skills matching job requirements |
| `missing_skills` | JSON | Required skills candidate lacks |
| `keyword_score` | Float | Skill overlap ratio (0.0-1.0) |
| `semantic_similarity` | Float | Embedding cosine similarity |
| `experience_match_score` | Float | Experience ratio score |
| `final_score` | Float | Combined weighted score |
| `explanation` | String | Human-readable scoring explanation |

---

#### Resume Batches Table

Tracks resume upload batches and their processing status.

```sql
CREATE TABLE resume_batches (
    batch_id TEXT PRIMARY KEY,
    total_files INTEGER NOT NULL,
    processed_files INTEGER DEFAULT 0,
    done_files INTEGER DEFAULT 0,
    needs_review_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `batch_id` | UUID | Unique batch identifier |
| `total_files` | Integer | Total resumes in batch |
| `processed_files` | Integer | Completed/failed count |
| `done_files` | Integer | Successfully processed count |
| `needs_review_files` | Integer | Count needing manual review |
| `failed_files` | Integer | Failed processing count |

---

#### Batch Items Table

Individual resume entries within batches.

```sql
CREATE TABLE batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    candidate_id TEXT,
    status TEXT DEFAULT 'QUEUED',
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES resume_batches(batch_id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
);
```

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `id` | Integer | Primary key |
| `batch_id` | UUID | Foreign key to batch |
| `file_name` | String | Resume filename |
| `candidate_id` | UUID | Links to processed candidate |
| `status` | Enum | QUEUED, PROCESSING, DONE, NEEDS_REVIEW, FAILED |
| `error` | String | Error message if processing failed |

---

## ChromaDB Vector Store Design

### Purpose

ChromaDB stores vector embeddings for semantic similarity search between resumes and job descriptions.

### Collection Schema

```python
collection_name = "resume_embeddings"

# Each record structure:
{
    "ids": [candidate_id],           # UUID as string
    "embeddings": [[0.1, 0.2, ...]], # 384-dim vector (all-MiniLM-L6-v2)
    "documents": [resume_text],      # Full resume text
    "metadatas": [{
        "candidate_name": "Jane Doe",
        "filename": "resume.pdf"
    }]
}
```

### Embedding Strategy

1. **Model**: `all-MiniLM-L6-v2` (384 dimensions, CPU-optimized)
2. **Generation**: Batch encoding with `model.encode(texts, batch_size=16, normalize_embeddings=True)`
3. **Storage**: Each candidate's full resume text is embedded and stored
4. **Query**: For job matching, job description is embedded and queried against candidate vectors

### Distance Metric

Cosine similarity is used (vectors are normalized, making cosine equivalent to dot product).

---

## Batch Processing in Database

### Flow

1. **Batch Creation** (`POST /resumes/batch-upload`)
   - `resume_batches` record created with `total_files` count
   - `batch_items` records created for each uploaded file
   - Initial status: `QUEUED` for all items

2. **Processing** (background task)
   - Each `batch_item` status updated to `PROCESSING`
   - On success:
     - `candidates` record created
     - `batch_item.candidate_id` set
     - `batch_item.status` set to `DONE`
     - `vector_store` upsert with embedding
   - On failure:
     - `batch_item.status` set to `NEEDS_REVIEW` or `FAILED`
     - `batch_item.error` populated with error message

3. **Status Polling** (`GET /resumes/batch/{batch_id}/status`)
   - Query `resume_batches` and `batch_items` tables
   - Aggregate counts returned (done, needs_review, failed, processed)

### SQL Indexes

```sql
-- Performance indexes
CREATE INDEX idx_candidates_batch_id ON candidates(batch_id);
CREATE INDEX idx_candidates_status ON candidates(status);
CREATE INDEX idx_match_results_job_id ON match_results(job_id);
CREATE INDEX idx_match_results_final_score ON match_results(final_score DESC);
CREATE INDEX idx_batch_items_batch_id ON batch_items(batch_id);
CREATE INDEX idx_batch_items_status ON batch_items(status);
```

---

## Current Implementation vs. Design

### Differences

| Aspect | Current Implementation | Intended Design |
|--------|---------------------|---------------|
| **Storage** | `InMemoryRepository` | SQLite with aiosqlite |
| **Vector Store** | `InMemoryVectorStore` | ChromaDB persistent |
| **Persistence** | Lost on restart | Persistent across restarts |

### Current Code Location

- **SQLite (intended)**: `src/storage/db.py` - `InMemoryRepository` class
- **ChromaDB (intended)**: `src/storage/vector_store.py` - `InMemoryVectorStore` class

---

## Recommended Improvements

### 1. Migrate to SQLite

Replace `InMemoryRepository` with actual SQLite implementation using aiosqlite:

```python
# src/storage/db.py
class SQLiteRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            # Create tables...
```

**Benefits:**
- Persistent storage survives application restarts
- WAL mode enables concurrent readers
- ACID compliance for data integrity
- Scalable for large candidate pools

### 2. Migrate to ChromaDB Persistent

Replace `InMemoryVectorStore` with ChromaDB client:

```python
# src/storage/vector_store.py
import chromadb

class ChromaVectorStore:
    def __init__(self, persist_dir: str, collection_name: str):
        client = chromadb.PersistentClient(path=persist_dir)
        self._collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
```

**Benefits:**
- Persistent embeddings survive restarts
- Optimized HNSW index for fast similarity search
- Scalable to millions of candidates
- Built-in metadata filtering

### 3. Add Database Migrations

Create migration scripts for schema evolution:

```
scripts/
├── migrate.py          # Migration runner
└── migrations/
    ├── 001_initial.sql
    ├── 002_add_indexes.sql
    └── 003_add_constraints.sql
```

### 4. Implement Connection Pooling

For production workloads, use connection pooling:

```python
from aiosqlite import Connection

# Use pool of connections instead of single connection
# Consider `databases` library for async pooling
```

### 5. Add Soft Deletes

Consider adding `deleted_at` timestamp for soft deletion:

```sql
ALTER TABLE candidates ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE jobs ADD COLUMN deleted_at TIMESTAMP;
```

### 6. Add Audit Trail

Track who uploaded/matched candidates:

```sql
ALTER TABLE resume_batches ADD COLUMN uploaded_by TEXT;
ALTER TABLE match_results ADD COLUMN matched_at TIMESTAMP;
```

---

## Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐
│  resume_batches  │       │      jobs        │
│──────────────────│       │──────────────────│
│ batch_id (PK)    │──────▶│ job_id (PK)      │
│ total_files      │       │ title            │
│ processed_files  │       │ required_skills  │
│ done_files       │       │ min_years        │
│ ...              │       │ ...              │
└────────┬─────────┘       └──────────▲───────┘
         │                            │
         ▼                            │
┌──────────────────┐                 │
│   batch_items    │                 │
│──────────────────│                 │
│ id (PK)          │                 │
│ batch_id (FK)    │                 │
│ file_name        │                 │
│ candidate_id (FK)│                 │
│ status           │                 │
│ error            │                 │
└────────┬─────────┘                 │
         │                            │
         ▼                            │
┌──────────────────┐                 │
│   candidates     │                 │
│──────────────────│                 │
│ candidate_id (PK)│                 │
│ batch_id (FK)    │                 │
│ full_name        │                 │
│ email            │                 │
│ ...              │                 │
└──────────────────┘                 │
                                       │
                                       ▼
┌──────────────────┐
│  match_results   │
│──────────────────│
│ result_id (PK)   │
│ job_id (FK)      │
│ candidate_id (FK)│
│ rank             │
│ final_score      │
│ ...              │
└──────────────────┘


┌──────────────────┐
│  ChromaDB        │
│  Collection      │
│──────────────────│
│ candidate_id     │──▶ Embeds resume text
│ embedding (384d) │
│ metadata         │
└──────────────────┘
```

---

## Performance Considerations

1. **Batch Size Limits**: Process resume embeddings in batches of 16 for efficiency
2. **WAL Mode**: SQLite WAL enables concurrent reads during writes
3. **Index Strategy**: Index frequently queried columns (job_id, status)
4. **Memory Management**: Use `PRAGMA cache_size` for SQLite in-memory caching
5. **Embedding Caching**: ChromaDB persists embeddings; no recompute needed