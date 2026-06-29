import time

import httpx
import pandas as pd
import streamlit as st

API_BASE = "http://localhost:8000"


def poll_match_results(job_id: str, batch_id: str | None = None, timeout_seconds: int = 30, interval_seconds: float = 1.5):
    """Poll until we receive a payload. Even if the results list is empty,
    return the latest payload so the UI can render 0/empty states reliably."""

    deadline = time.monotonic() + timeout_seconds
    last_payload = None

    while time.monotonic() < deadline:
        params: dict[str, str] = {"job_id": job_id}
        if batch_id:
            params["batch_id"] = batch_id
        results_resp = httpx.get(
            f"{API_BASE}/match/results",
            params=params,
            timeout=30,
        )
        if results_resp.status_code != 200:
            return None

        last_payload = results_resp.json()
        # return as soon as the backend includes the results key
        if isinstance(last_payload, dict) and "results" in last_payload:
            return last_payload

        time.sleep(interval_seconds)

    return last_payload

st.set_page_config(page_title="Resume Analyzer", layout="wide")
st.title("AI-Powered Resume Screening & Candidate Ranking")
st.caption("Uploads resume batches, analyzes job descriptions, and ranks candidates using the API backend.")

tab_upload, tab_job, tab_results = st.tabs(["📄 Upload Resumes", "📋 Job Description", "🏆 Rankings"])

# ---------------- Upload Tab ----------------
with tab_upload:
    st.subheader("Upload Resumes (PDF)")
    files = st.file_uploader("Choose resume PDFs", type=["pdf"], accept_multiple_files=True)

    if st.button("Upload & Process", disabled=not files):
        with st.spinner("Uploading..."):
            upload_files = [("files", (f.name, f.getvalue(), "application/pdf")) for f in files]
            resp = httpx.post(f"{API_BASE}/resumes/batch-upload", files=upload_files, timeout=30)
            if resp.status_code == 202:
                batch_id = resp.json()["batch_id"]
                st.session_state["batch_id"] = batch_id
                st.success(f"Batch queued: {batch_id}")
            else:
                st.error(f"Upload failed: {resp.text}")

    if "batch_id" in st.session_state:
        st.divider()
        st.write("**Batch status:**")
        placeholder = st.empty()
        if st.button("Refresh status"):
            try:
                status_resp = httpx.get(f"{API_BASE}/resumes/batch/{st.session_state['batch_id']}/status", timeout=30)
                if status_resp.status_code == 200:
                    data = status_resp.json()
                    placeholder.json(data)
                else:
                    placeholder.error(f"Could not fetch status: HTTP {status_resp.status_code}")
            except httpx.ReadTimeout:
                placeholder.error("Request timed out - the server may be busy or unavailable")
            except httpx.ConnectError:
                placeholder.error("Could not connect to server - is the API running?")
            except Exception as e:
                placeholder.error(f"Error fetching status: {e}")

# ---------------- Job Description Tab ----------------
with tab_job:
    st.subheader("Submit Job Description")
    jd_text = st.text_area("Job description", placeholder="Enter the full job description here...", height=150)
    jd_title = st.text_input("Job title", placeholder="e.g., Senior Python Backend Engineer")
    min_years = st.number_input("Minimum years experience", min_value=0.0, step=0.5, value=None, placeholder="Optional: 3.5")

    # Validation
    missing_fields = []
    if not jd_text:
        missing_fields.append("Job description")
    if not jd_title:
        missing_fields.append("Job title")

    analyze_disabled = bool(missing_fields)

    if analyze_disabled:
        st.warning(f"Please fill in the following required field(s): {', '.join(missing_fields)}")

    if st.button("Analyze Job Description", disabled=analyze_disabled):
        with st.spinner("Analyzing..."):
            resp = httpx.post(
                f"{API_BASE}/jobs/analyze",
                json={"title": jd_title, "description": jd_text, "minimum_years_experience": min_years if min_years is not None else 0},
                timeout=30,
            )
            if resp.status_code == 201:
                job = resp.json()["job"]
                st.session_state["job_id"] = job["job_id"]
                st.session_state.pop("match_results", None)
                st.session_state.pop("match_results_job_id", None)
                st.success(f"Job analyzed: {job['job_id']}")
                st.json(job)
            else:
                st.error(f"Analysis failed: {resp.text}")

# ---------------- Rankings Tab ----------------
with tab_results:
    st.subheader("Candidate Rankings")

    if "job_id" not in st.session_state:
        st.info("Submit a job description first.")
    elif "batch_id" not in st.session_state:
        st.info("Upload resumes first.")
    else:
        job_id = str(st.session_state["job_id"])
        batch_id = str(st.session_state["batch_id"])
        payload = st.session_state.get("match_results") if st.session_state.get("match_results_job_id") == job_id else None

        if st.button("Run Matching"):
            with st.spinner("Scoring candidates..."):
                resp = httpx.post(
                    f"{API_BASE}/match/run", params={"job_id": job_id, "batch_id": batch_id}, timeout=60
                )
                if resp.status_code != 202:
                    st.error(f"Matching failed: {resp.text}")
                else:
                    st.session_state["match_results"] = poll_match_results(job_id, batch_id=batch_id)
                    st.session_state["match_results_job_id"] = job_id if st.session_state["match_results"] is not None else None
                    if st.session_state["match_results"] is None:
                        st.warning("Matching is still running. Refresh this tab in a few seconds.")
        if not payload:
            st.info("Run matching to load rankings.")
        else:
            results = payload.get("results", [])
            if not results:
                st.warning("No results yet — matching is still running or no candidates were available.")
            else:
                df = pd.DataFrame(
                    [
                        {
                            "Rank": r["rank"],
                            "Candidate": r.get("candidate_name", r["candidate_id"]),
                            "Candidate ID": r["candidate_id"],
                            "Score": f"{r['score_breakdown']['final_score'] * 100:.1f}%",
                            "Matched Skills": ", ".join(r["score_breakdown"]["matched_skills"]),
                            "Missing Skills": ", ".join(r["score_breakdown"]["missing_skills"]),
                            "Experience": r["score_breakdown"]["experience_match"],
                        }
                        for r in results
                    ]
                )
                st.dataframe(df, use_container_width=True, column_config={"Candidate ID": st.column_config.Column(width="small")})

                st.divider()
                st.subheader("Candidate Detail")
                selected = st.selectbox(
                    "Select candidate",
                    [r["candidate_id"] for r in results],
                    format_func=lambda v: next(
                        (r.get("candidate_name", r["candidate_id"]) for r in results if r["candidate_id"] == v),
                        str(v),
                    ),
                    key="selected_candidate",
                )
                detail = next(r for r in results if r["candidate_id"] == selected)


                st.write(f"**Explanation:** {detail['score_breakdown']['explanation']}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Keyword Score", f"{detail['score_breakdown']['keyword_score']:.2f}")
                col2.metric("Semantic Similarity", f"{detail['score_breakdown']['semantic_similarity']:.2f}")
                col3.metric("Final Score", f"{detail['score_breakdown']['final_score']:.2f}")

                try:
                    cand_resp = httpx.get(f"{API_BASE}/resumes/candidates/{selected}", timeout=15)
                    if cand_resp.status_code == 200:
                        cand = cand_resp.json()
                        with st.expander("Full Extracted Profile", expanded=True):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.subheader("Education")
                                for item in cand.get("education", []):
                                    st.write(f"- {item}")
                                st.subheader("Certifications")
                                for item in cand.get("certifications", []):
                                    st.write(f"- {item}")
                                st.subheader("Strengths")
                                for item in cand.get("strengths", []):
                                    st.success(f"- {item}")
                            with c2:
                                st.subheader("Work Experience")
                                for item in cand.get("work_experience", []):
                                    st.write(f"- {item}")
                                st.subheader("Projects")
                                for item in cand.get("projects", []):
                                    st.write(f"- {item}")
                                st.subheader("Weaknesses")
                                for item in cand.get("weaknesses", []):
                                    st.warning(f"- {item}")

                            st.divider()
                            st.subheader("Skills")
                            confirmed = cand.get("confirmed_skills", [])
                            unverified = cand.get("unverified_skills", [])
                            if confirmed:
                                st.write("**Confirmed Skills** (verified from resume text)")
                                st.write(", ".join(confirmed))
                            if unverified:
                                st.warning("**Unverified Skills** (could not find supporting evidence in resume text)")
                                st.write(", ".join(unverified))

                            st.divider()
                            st.subheader("Gap Analysis")
                            missing = detail["score_breakdown"]["missing_skills"]
                            weaknesses = cand.get("weaknesses", [])
                            if missing or weaknesses:
                                gc1, gc2 = st.columns(2)
                                with gc1:
                                    st.write("**Missing Skills** (required by job, not found in resume)")
                                    for item in missing:
                                        st.error(f"- {item}")
                                with gc2:
                                    st.write("**Candidate Weaknesses** (identified from resume gaps)")
                                    for item in weaknesses:
                                        st.warning(f"- {item}")
                            else:
                                st.success("No significant gaps identified.")
                    else:
                        st.info("Could not load candidate details.")
                except Exception:
                    st.info("Could not load candidate details.")
                #except Exception:
                #    st.info("Could not load candidate details.")

                st.download_button(
                    "Export Results as CSV",
                    data=df.to_csv(index=False),
                    file_name="candidate_rankings.csv",
                    mime="text/csv",
                )

with st.sidebar:
    st.header("Testing Notes")
    st.write("Use the API docs in docs/api_testing_guide.md for Postman.")
    st.write("Background processing is async + semaphore-based for CPU/LLM separation; Celery workers are scaffolded separately.")