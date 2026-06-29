# Deliverables

## 1. Complete Source Code

The complete source code is available in this repository under the `/src` directory, including all application modules:

| Module | Description |
|--------|-------------|
| `src/main.py` | FastAPI application entry point |
| `src/pipeline.py` | Orchestration layer |
| `src/core/` | Schemas, config, and exceptions |
| `src/api/` | Resume, job, and matching endpoints |
| `src/ingestion/` | PDF text extraction |
| `src/extraction/` | Rule-based and LLM extraction |
| `src/jobspec/` | Job description analysis |
| `src/matching/` | Keyword and semantic matching |
| `src/ranking/` | Score combination and explanation |
| `src/storage/` | SQLite and ChromaDB storage |
| `src/ui/` | Streamlit frontend |
| `workers/` | Background task processing |

## 2. GitHub Repository

The project source code, issues, and pull requests are hosted at:

- **URL**: https://github.com/M-codeR-UMER/resume_analyzer.git

## 3. README Documentation

The main project README provides setup instructions, architecture overview, and usage guidelines:

- **File**: [`README.md`](../README.md)

## 4. Sample Dataset / Testing Data

Sample resumes and job descriptions are included for testing:

- **Sample Resumes**: [`/data/sample_resumes`](../data/sample_resumes)
  - `john_smith_resume.pdf`
  - `jane_doe_resume.pdf`
  - `jane_doe_resume.txt`

- **Sample Job Descriptions**: [`/data/sample_jds`](../data/sample_jds)
  - `python_backend_engineer.txt`

## 5. Model Documentation

- **Scoring Methodology**: [`/docs/scoring_methodology.md`](scoring_methodology.md) — Details on how candidate scores are calculated using keyword overlap, semantic similarity, and experience matching.
- **Database Design**: [`/docs/database_design.md`](database_design.md) — Schema and data models.
- **API Testing Guide**: [`/docs/api_testing_guide.md`](api_testing_guide.md) — Manual testing instructions.

## 6. Demo Video

A recorded demo of the Resume Analyzer application is available here:

**File**: [Resume Analyzer - Google Chrome 2026-06-29 23-39-45.mp4](../Resume Analyzer - Google Chrome 2026-06-29 23-39-45.mp4)
