# Scoring Methodology

## Overview

The Resume Analyzer uses a hybrid scoring approach that combines multiple signals to rank candidates against job requirements. Each match produces an explainable score breakdown that helps recruiters understand why a candidate was ranked a certain way.

## Final Score Formula

```
final_score = W_keyword × keyword_score + W_semantic × semantic_similarity + W_experience × experience_match_score
```

Where weights are configurable (default values):
- `W_keyword = 0.4` (40%)
- `W_semantic = 0.4` (40%)
- `W_experience = 0.2` (20%)

All scores are normalized to the range [0.0, 1.0].

---

## Component Scores

### 1. Keyword Score (40%)

**Purpose**: Measures skill overlap between candidate and job requirements.

**Calculation**:
```
keyword_score = |matched_required_skills| / |total_required_skills|
```

Where `matched_required_skills` are skills from the job description that were verified in the candidate's resume text (either verbatim or via fuzzy matching with ≥0.86 similarity ratio).

**Example**:
- Job requires: `["python", "fastapi", "sql", "docker"]`
- Candidate has verified: `["python", "fastapi", "sql"]`
- Keyword score: 3/4 = 0.75

**Benefits**:
- Direct, interpretable measure of skill fit
- Validates against actual resume content
- Excludes unverified skills from scoring

---

### 2. Semantic Similarity (40%)

**Purpose**: Measures overall textual similarity between candidate experience and job responsibilities.

**Method**:
1. Generate embeddings using `all-MiniLM-L6-v2` (384 dimensions)
2. Normalize embeddings to unit vectors
3. Compute cosine similarity: `candidate_vector · job_vector`

**Fallback**: If sentence-transformers unavailable, uses Jaccard-like term overlap:
```
term_overlap = |candidate_terms ∩ job_terms| / |candidate_terms ∪ job_terms|
```

**Example**:
- Resume: "5 years Python backend development with FastAPI and SQL databases"
- Job: "Python backend engineer with FastAPI experience required"
- Semantic similarity: ~0.76 (high overlap in concepts)

**Benefits**:
- Captures implicit skill mentions
- Understands semantic equivalence ("Postgres" ≈ "SQL")
- Weighted equally with keyword matching

---

### 3. Experience Match Score (20%)

**Purpose**: Quantifies experience level alignment.

**Calculation**:
```
experience_match_score = min(max(candidate_years / required_years, 0.0), 1.0)
```

**Cases**:
- If `required_years = 0`: Score is 1.0 if candidate has any experience, 0 otherwise
- If `candidate_years >= required_years`: Score between 0.0-1.0 based on surplus
- If `candidate_years < required_years`: Score < 1.0 based on deficit

**Example**:
- Required: 3 years
- Candidate: 4.5 years
- Experience match score: min(4.5/3, 1.0) = 1.0 (exceeds requirement)

**Text Message**:
- Surplus: "Candidate exceeds required experience by X years"
- Deficit: "Candidate is short of required experience by X years"

---

## Score Breakdown Output

Each match result includes:

```json
{
  "matched_skills": ["python", "fastapi", "sql"],
  "missing_skills": ["redis"],
  "keyword_score": 0.82,
  "semantic_similarity": 0.76,
  "experience_match_score": 1.0,
  "final_score": 0.79,
  "explanation": "Candidate matched 3/4 required skills and exceeds required experience by 1 year."
}
```

### Fields Explained

| Field | Description |
|-------|-------------|
| `matched_skills` | Skills from job requirements found in candidate resume |
| `missing_skills` | Required skills not verified in candidate resume |
| `keyword_score` | Ratio of verified skill matches (0.0-1.0) |
| `semantic_similarity` | Embedding cosine similarity or term overlap (0.0-1.0) |
| `experience_match_score` | Experience alignment score (0.0-1.0) |
| `final_score` | Weighted combination of all three scores |
| `explanation` | Human-readable summary of match quality |

---

## Ranking Algorithm

1. Compute scores for all candidates against a job
2. Sort by `final_score` in descending order
3. Assign ranks starting from 1

```python
results = candidates.map(lambda c: compute_scores(c, job))
results.sort(key=lambda r: r.score_breakdown.final_score, reverse=True)
results = results.enumerate(start=1)  # Assign ranks
```

---

## Configuration

Scoring weights are configurable via environment variables:

```env
WEIGHT_KEYWORD_SCORE=0.4
WEIGHT_SEMANTIC_SCORE=0.4
WEIGHT_EXPERIENCE_SCORE=0.2
```

The weights should sum to 1.0. Adjust based on hiring priorities:
- Higher `WEIGHT_KEYWORD_SCORE`: Prioritize exact skill matches
- Higher `WEIGHT_SEMANTIC_SCORE`: Prioritize cultural/conceptual fit
- Higher `WEIGHT_EXPERIENCE_SCORE`: Prioritize seniority level

---

## Anti-Hallucination Measures

### Skill Verification

Extracted skills are cross-checked against resume text:

1. **Exact match**: Skill text appears verbatim in resume
2. **Fuzzy match**: SequenceMatcher ratio ≥ 0.86
3. **Unverified skills**: Skills claimed by LLM but not found in text are stored separately and excluded from scoring

This prevents:
- LLM hallucinating skills not present in resume
- Candidates being over-ranked due to false positives

---

## Example Scenarios

### Strong Match (Score: ~0.95)

**Job**: "Senior Python backend engineer. 5+ years experience. Skills: Python, FastAPI, SQL, Docker, AWS"

**Candidate**: "6 years Python development. Built FastAPI services with PostgreSQL. Docker experience. AWS certified."

| Component | Score | Reasoning |
|-----------|-------|-----------|
| Keyword | 1.0 | All 5 skills matched |
| Semantic | ~0.9 | High textual overlap |
| Experience | 1.0 | 6/5 years = exceeds |

### Moderate Match (Score: ~0.6)

**Job**: "Python developer. 3+ years. Skills: Python, React, SQL"

**Candidate**: "Python engineer. 2 years experience. FastAPI, Django."

| Component | Score | Reasoning |
|-----------|-------|-----------|
| Keyword | 0.67 | Only "Python" matched (1/3 skills) |
| Semantic | ~0.6 | Some overlap in backend concepts |
| Experience | 0.67 | 2/3 years = short by 1 year |

### Weak Match (Score: ~0.2)

**Job**: "Frontend React developer. 5+ years"

**Candidate**: "Backend Python engineer. 2 years"

| Component | Score | Reasoning |
|-----------|-------|-----------|
| Keyword | 0.0 | No matching skills |
| Semantic | ~0.2 | Minimal overlap |
| Experience | 0.4 | 2/5 years = short by 3 years |

---

## Implementation Reference

- **Keyword Matcher**: `src/matching/keyword_matcher.py`
- **Semantic Matcher**: `src/matching/semantic_matcher.py`
- **Scorer**: `src/ranking/scorer.py`
- **Configuration**: `src/core/config.py`