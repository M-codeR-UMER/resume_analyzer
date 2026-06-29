# Resume Analyzer API Testing Guide

This document is for manual testing in Postman against the current FastAPI backend.

## Base URL

- Local default: `http://127.0.0.1:8000`
- Health check: `GET /health`

## Common Rules

- Send JSON requests with `Content-Type: application/json`.
- Upload resumes with `multipart/form-data`.
- `batch-upload` and `match/run` are asynchronous entry points. They return immediately and do not process inline.
- UUID values are required for `batch_id`, `job_id`, `candidate_id`, and `result_id` fields.

## Endpoints

### 1) Health Check

`GET /health`

Purpose:
- Confirms the API process is running.

Response:

```json
{
  "status": "ok"
}
```

---

### 2) Upload Resume Batch

`POST /resumes/batch-upload`

Purpose:
- Accepts multiple PDF resumes.
- Creates a batch record immediately.
- Starts background processing for each uploaded file.

Request type:
- `multipart/form-data`

Form field:
- `files`: one or more PDF files

Postman setup:
- Method: `POST`
- URL: `{{base_url}}/resumes/batch-upload`
- Body: `form-data`
- Key: `files`
- Type: `File`
- Select multiple PDF files by adding repeated `files` entries

Response status:
- `202 Accepted`

Example response:

```json
{
  "batch_id": "7e7a7d30-7f7d-4f1d-b2c5-4d4a3c6d9e11",
  "accepted_files": 3,
  "status": "ACCEPTED"
}
```

Background flow:
- PDF text extraction runs in a process pool.
- Rule-based extraction runs first.
- Groq structured extraction runs with validation and retry.
- Candidate is saved.
- Vector embedding is created and stored.
- Batch item status becomes `DONE` or `NEEDS_REVIEW`.

---

### 3) Check Batch Status

`GET /resumes/batch/{batch_id}/status`

Purpose:
- Polls batch progress until all items are processed.

Path parameter:
- `batch_id`: UUID from the upload response

Response status:
- `200 OK`
- `404 Not Found` if the batch does not exist

Example response:

```json
{
  "batch_id": "7e7a7d30-7f7d-4f1d-b2c5-4d4a3c6d9e11",
  "total_files": 3,
  "processed_files": 2,
  "done_files": 1,
  "needs_review_files": 1,
  "failed_files": 0,
  "items": [
    {
      "file_name": "resume1.pdf",
      "candidate_id": "d2f6e9e0-1c42-4d4a-a6f7-4c1d5a7d2c91",
      "status": "DONE",
      "error": null
    },
    {
      "file_name": "resume2.pdf",
      "candidate_id": null,
      "status": "NEEDS_REVIEW",
      "error": "No text could be extracted from the uploaded resume"
    }
  ],
  "created_at": "2026-06-26T12:00:00Z"
}
```

Status meanings:
- `QUEUED`: batch item created, not yet processed
- `PROCESSING`: extraction in progress
- `DONE`: candidate saved successfully
- `NEEDS_REVIEW`: extraction or validation failed
- `FAILED`: reserved status

---

### 4) Analyze Job Description

`POST /jobs/analyze`

Purpose:
- Parses a job description into structured job requirements.

Request type:
- `application/json`

Body:

```json
{
  "title": "Python Backend Engineer",
  "description": "We need a Python backend engineer with FastAPI, SQL, and 3+ years of experience.",
  "minimum_years_experience": 3
}
```

Note: `title` and `description` are required fields. `minimum_years_experience` defaults to 0 if omitted.

Response status:
- `201 Created`

Example response:

```json
{
  "job": {
    "job_id": "0f2d4c95-4cf2-4b63-bb14-4ee35c3a3e10",
    "title": "Python Backend Engineer",
    "description": "We need a Python backend engineer with FastAPI, SQL, and 3+ years of experience.",
    "required_skills": ["python", "fastapi", "sql"],
    "preferred_skills": [],
    "minimum_years_experience": 3,
    "raw_text": "We need a Python backend engineer with FastAPI, SQL, and 3+ years of experience.",
    "created_at": "2026-06-26T12:05:00Z"
  }
}
```

---

### 5) Run Matching

`POST /match/run?job_id={job_id}&batch_id={batch_id}`

Purpose:
- Scores candidates against one analyzed job.
- If `batch_id` is provided, only candidates from that batch are scored.
- If `batch_id` is omitted, all stored candidates are scored.

Query parameters:
- `job_id`: UUID from the job analyze response (required)
- `batch_id`: UUID from the resume upload batch (optional)

Response status:
- `202 Accepted`
- `404 Not Found` if the job does not exist

Example response:

```json
{
  "job_id": "0f2d4c95-4cf2-4b63-bb14-4ee35c3a3e10",
  "status": "DONE",
  "matched_candidates": 12
}
```

Matching behavior:
- Keyword score is computed first.
- Semantic score is computed next.
- Final ranking is built from the scorer output.
- Results are stored for later retrieval.

---

### 6) Get Match Results

`GET /match/results?job_id={job_id}`

Purpose:
- Returns ranked candidates and score breakdowns for one job.

Query parameter:
- `job_id`: UUID from the job analyze response

Response status:
- `200 OK`
- `404 Not Found` if the job does not exist

Example response:

```json
{
  "job_id": "0f2d4c95-4cf2-4b63-bb14-4ee35c3a3e10",
  "results": [
    {
      "result_id": "4f2d7f90-8b7f-48da-9b5f-4fb8fdf5d381",
      "job_id": "0f2d4c95-4cf2-4b63-bb14-4ee35c3a3e10",
      "candidate_id": "d2f6e9e0-1c42-4d4a-a6f7-4c1d5a7d2c91",
      "candidate_name": "Jane Doe",
      "rank": 1,
      "status": "DONE",
      "score_breakdown": {
        "matched_skills": ["python", "fastapi", "sql"],
        "missing_skills": ["redis"],
        "experience_match": "Candidate exceeds required experience by 1.5 years.",
        "keyword_score": 0.82,
        "semantic_similarity": 0.76,
        "experience_match_score": 1,
        "final_score": 0.79,
        "explanation": "Candidate matched 3/4 required skills and exceeds required experience by 1.5 years."
      },
      "created_at": "2026-06-26T12:10:00Z"
    }
  ]
}
```

## Recommended Postman Flow

1. Upload resumes with `POST /resumes/batch-upload`.
2. Copy the returned `batch_id`.
3. Poll `GET /resumes/batch/{batch_id}/status` until all items are `DONE` or `NEEDS_REVIEW`.
4. Submit the job with `POST /jobs/analyze` (title and description are required).
5. Copy the returned `job.job_id`.
6. Trigger scoring with `POST /match/run?job_id=...&batch_id=...` (optional batch_id to filter candidates).
7. Fetch ranked results with `GET /match/results?job_id=...`.

## Error Response Shape

Most API errors return:

```json
{
  "detail": "message here"
}
```

Common cases:
- `404 Not Found` for missing batch or job IDs
- `422 Unprocessable Entity` for invalid request payloads, invalid UUIDs, or missing required fields (title, description)

## Notes For Testing

- Use small PDF samples first.
- Expect resume processing to remain async after upload.
- If a resume cannot be validated, the batch item should move to `NEEDS_REVIEW`.
- `score_breakdown.semantic_similarity` is supporting detail only; the main ranking field is `final_score`.