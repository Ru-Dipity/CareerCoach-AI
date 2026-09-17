import os
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.utils.helpers import *
from src.generator.question_generator import QuestionGenerator
from src.config.settings import settings
from src.parser.job_parser import (
    SkillExtractor,
    SkillQuestionGenerator,
    CANONICAL_CATEGORIES,
)
from src.generator.matcher import ProfileJobMatcher

load_dotenv()


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extracts raw text from an uploaded PDF resume.

    Delegates to the shared ``extract_text_from_pdf`` helper so the parsing
    logic lives in exactly one place. Returns an empty string on failure and
    surfaces the reason to the caller via the raised CustomException message.
    """
    from src.utils.pdf_loader import extract_text_from_pdf

    return extract_text_from_pdf(file_bytes)


def _reset_quiz_state():
    st.session_state.quiz_manager = QuizManager()
    st.session_state.quiz_generated = False
    st.session_state.quiz_submitted = False
    st.session_state.extracted_skills = None
    st.session_state.job_alignment_report = None
    st.session_state.candidate_match_result = None
    st.session_state.saved_results_file = None
    st.session_state.saved_match_file = None
    # Clear widget-backed keys so stale job text / answers do not survive a reset.
    for key in ("job_text_input", "cv_text_input", "cv_pdf_uploader"):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if (
            key.startswith("mcq_")
            or key.startswith("fill_blank_")
            or key.startswith("_pdf_text::")
        ):
            st.session_state.pop(key, None)


def _render_skill_preview(extracted):
    st.subheader("📊 Extracted Skills & Market Analytics")
    summary_rows = []
    for skill in extracted.skills:
        summary_rows.append({
            "Skill": skill.skill_name,
            "Category": skill.category,
            "Occurrences": skill.occurrence_count,
        })
    preview_df = pd.DataFrame(summary_rows)
    
    col1, col2, _ = st.columns([1, 1, 2])
    if extracted.role_title:
        col1.write(f"**Role:** {extracted.role_title}")
    if extracted.seniority:
        col2.write(f"**Seniority:** {extracted.seniority}")

    # Tabs for raw data vs interactive chart visualization
    tab_table, tab_chart = st.tabs(["📋 Skill Table", "📈 Skill Distribution Charts"])
    with tab_table:
        st.dataframe(preview_df, use_container_width=True, hide_index=True)
        st.caption(f"Total unique skills extracted: {len(extracted.skills)}")

    with tab_chart:
        if not preview_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                # Skill category breakdown
                cat_counts = preview_df["Category"].value_counts().reset_index()
                cat_counts.columns = ["Category", "Count"]
                fig_pie = px.pie(
                    cat_counts,
                    values="Count",
                    names="Category",
                    title="Skills by Category",
                    hole=0.4,
                )
                fig_pie.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=300)
                st.plotly_chart(fig_pie, use_container_width=True)

            with c2:
                # Top demanded skills
                top_skills = preview_df.sort_values(by="Occurrences", ascending=True).tail(10)
                fig_bar = px.bar(
                    top_skills,
                    x="Occurrences",
                    y="Skill",
                    orientation="h",
                    title="Top Required Technologies",
                    color="Category",
                )
                fig_bar.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=300)
                st.plotly_chart(fig_bar, use_container_width=True)


def _render_candidate_matcher(job_text: str, provider: str = "groq"):
    """Renders candidate profile input and visual match diagnostics."""
    with st.expander("👤 Candidate Profile & Fit Assessment (Optional)", expanded=False):
        st.caption("Upload your CV or paste a summary to analyze alignment against this job.")
        
        mode = st.radio("Input Format:", ["Plain Text / Bio", "Upload Resume (PDF)"], horizontal=True)
        candidate_text = ""
        
        if mode == "Upload Resume (PDF)":
            uploaded_pdf = st.file_uploader("Upload PDF Resume", type=["pdf"], key="cv_pdf_uploader")
            if uploaded_pdf is not None:
                # ``UploadedFile`` subclasses ``io.BytesIO``: ``read()`` advances
                # an internal cursor and returns b"" once exhausted, whereas
                # ``getvalue()`` always returns the full buffer regardless of
                # cursor position. Streamlit reruns this whole script on every
                # interaction, so we must use the cursor-independent accessor.
                #
                # The cache key includes ``file_id`` (unique per upload) so that
                # re-uploading a file with the same name/size still refreshes
                # the entry instead of reusing a stale result.
                file_id = getattr(uploaded_pdf, "file_id", None) or uploaded_pdf.name
                cache_key = f"_pdf_text::{file_id}::{uploaded_pdf.name}::{uploaded_pdf.size}"
                error_key = f"{cache_key}::error"

                if cache_key not in st.session_state:
                    try:
                        raw_bytes = uploaded_pdf.getvalue()
                        extracted = _extract_pdf_text(raw_bytes)
                        # Only cache a *successful* extraction. A failure must
                        # NOT poison the cache with an empty string, otherwise
                        # every later rerun would keep showing the warning even
                        # after the underlying problem is resolved.
                        st.session_state[cache_key] = extracted
                        st.session_state.pop(error_key, None)
                    except Exception as e:
                        st.session_state.pop(cache_key, None)
                        st.session_state[error_key] = str(e)

                candidate_text = st.session_state.get(cache_key, "")
                if candidate_text:
                    st.success(
                        f"Resume text extracted successfully! ({len(candidate_text)} characters)"
                    )
                else:
                    err = st.session_state.get(error_key)
                    if err:
                        st.error(f"Failed to read PDF file: {err}")
                    st.warning(
                        "No selectable text found in this PDF. It is most likely a "
                        "scanned/image-only document. Please switch **Input Format** "
                        "to `Plain Text / Bio` and paste your profile instead."
                    )
        else:
            candidate_text = st.text_area(
                "Paste your background, skills, or resume summary:",
                height=150,
                placeholder="E.g., 3 years experience in Python, AWS Cloud, Docker, Terraform...",
                key="cv_text_input",
            )

        if st.button("Evaluate Match & Skill Gaps"):
            if not job_text or not job_text.strip():
                st.warning("Please provide a Job Description in the sidebar first.")
            elif not candidate_text.strip():
                st.warning("Please provide your profile details or resume.")
            else:
                try:
                    matcher = ProfileJobMatcher(provider=provider)
                    with st.spinner("Analyzing candidate alignment & capability radar..."):
                        result = matcher.analyze_match(job_text, candidate_text)
                        st.session_state.candidate_match_result = result
                    st.success("Match report generated!")
                except Exception as e:
                    st.error(f"Failed to analyze match: {str(e)}")

        # Render report if available
        if st.session_state.get("candidate_match_result"):
            res = st.session_state.candidate_match_result
            st.markdown("---")
            
            m_col1, m_col2 = st.columns([1, 2])
            with m_col1:
                st.metric("Overall Match Fit", f"{res.overall_score}%")
                st.write("**Key Strengths:**")
                for s in res.strengths[:3]:
                    st.write(f"- ✅ {s}")
                st.write("**Key Missing/Gap Areas:**")
                for g in res.gap_analysis[:3]:
                    st.write(f"- ⚠️ {g}")

            with m_col2:
                # Plotly Radar Chart
                dims = [d.dimension for d in res.radar_data]
                job_r = [d.job_requirement for d in res.radar_data]
                cand_r = [d.candidate_capability for d in res.radar_data]
                
                dims.append(dims[0])
                job_r.append(job_r[0])
                cand_r.append(cand_r[0])
                
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(r=job_r, theta=dims, fill="toself", name="Job Requirement", line_color="#FF6384"))
                fig_radar.add_trace(go.Scatterpolar(r=cand_r, theta=dims, fill="toself", name="Your Profile", line_color="#36A2EB"))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    height=320,
                    margin=dict(l=30, r=30, t=30, b=30),
                    showlegend=True,
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            # Save / download the Match & Skill report (mirrors the quiz CSV flow).
            if st.button("Save Match Report"):
                saved_match = save_match_report_to_json(res)
                if saved_match:
                    st.session_state.saved_match_file = saved_match
                else:
                    st.warning("No match report available")

            saved_match_file = st.session_state.get("saved_match_file")
            if saved_match_file and os.path.exists(saved_match_file):
                with open(saved_match_file, "rb") as f:
                    st.download_button(
                        label="Download Match Report",
                        data=f.read(),
                        file_name=os.path.basename(saved_match_file),
                        mime="application/json",
                    )


def _render_alignment_report(alignment):
    if not alignment:
        return
    ratio_pct = round(alignment.get("ratio", 0.0) * 100, 1)
    aligned = alignment.get("aligned", 0)
    total = alignment.get("total", 0)
    st.subheader("Skill Coverage Report")
    st.write(f"**Questions aligned to extracted skills:** {aligned}/{total} ({ratio_pct}%)")
    unmapped = alignment.get("unmapped", [])
    if unmapped:
        with st.expander(f"View {len(unmapped)} questions with unmapped target_skill"):
            st.dataframe(pd.DataFrame(unmapped), use_container_width=True, hide_index=True)


def main():
    st.set_page_config(page_title="CareerCoach AI", page_icon="🎯", layout="wide")

    if "quiz_manager" not in st.session_state:
        st.session_state.quiz_manager = QuizManager()
    if "quiz_generated" not in st.session_state:
        st.session_state.quiz_generated = False
    if "quiz_submitted" not in st.session_state:
        st.session_state.quiz_submitted = False
    if "extracted_skills" not in st.session_state:
        st.session_state.extracted_skills = None
    if "job_alignment_report" not in st.session_state:
        st.session_state.job_alignment_report = None
    if "candidate_match_result" not in st.session_state:
        st.session_state.candidate_match_result = None
    if "saved_results_file" not in st.session_state:
        st.session_state.saved_results_file = None
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = "groq"

    st.title("CareerCoach AI")

    st.sidebar.header("Quiz Settings")

    st.sidebar.caption(f"Active LLM: **{st.session_state.llm_provider.title()}**")

    provider_label = st.sidebar.radio(
        "LLM Provider",
        ["Groq", "DeepSeek"],
        index=0 if st.session_state.llm_provider == "groq" else 1,
        help="Choose which LLM service generates the quiz. Each provider uses its own API key and model configuration.",
    )
    provider = provider_label.strip().lower()
    if provider != st.session_state.llm_provider:
        # Provider switch invalidates previously generated content.
        st.session_state.llm_provider = provider
        _reset_quiz_state()

    mode = st.sidebar.radio(
        "Quiz Mode",
        ["Topic Quiz", "Job Description Quiz"],
        index=0,
        help="Topic Quiz uses a single keyword. Job Description Quiz parses a full posting into skills then generates questions.",
    )

    question_type = st.sidebar.radio(
        "Select Question Type",
        ["Multiple Choice", "Fill in the Blank"],
        index=0,
        help="Choose how the quiz questions will be presented. Radio-only selection to avoid search-box edits.",
    )

    job_text = None
    if mode == "Topic Quiz":
        topic = st.sidebar.text_input("Enter Topic", placeholder="DevOps, Cloud Infrastructure")
    else:
        topic = None
        job_text = st.sidebar.text_area(
            "Paste Job Description",
            height=220,
            max_chars=settings.MAX_JOB_TEXT_LENGTH,
            placeholder="Paste a complete job posting here. Multi-line rich text, HTML, and bullet lists are all supported after sanitization.",
            key="job_text_input",
        )
        current_len = len(job_text) if job_text else 0
        pct = round((current_len / settings.MAX_JOB_TEXT_LENGTH) * 100, 0)
        st.sidebar.caption(
            f"Characters: {current_len}/{settings.MAX_JOB_TEXT_LENGTH} ({pct}%)"
        )

    difficulty = st.sidebar.selectbox(
        "Difficulty Level",
        ["Easy", "Medium", "Hard"],
        index=1,
    )

    num_questions = st.sidebar.number_input(
        "Number of Questions",
        min_value=1,
        max_value=10,
        value=5,
    )

    if st.sidebar.button("Reset Quiz"):
        _reset_quiz_state()
        rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("Generate Quiz"):
        st.session_state.quiz_submitted = False
        st.session_state.job_alignment_report = None

        if mode == "Topic Quiz":
            if not topic or not topic.strip():
                st.warning("Please enter a non-empty topic before generating the quiz.")
            else:
                generator = QuestionGenerator(provider=provider)
                with st.spinner("Generating quiz..."):
                    success = st.session_state.quiz_manager.generate_questions(
                        generator,
                        topic, question_type, difficulty, num_questions,
                    )
                st.session_state.quiz_generated = success
                st.session_state.extracted_skills = None
                rerun()
        else:
            extractor = SkillExtractor(provider=provider)
            ok, reason = extractor.validate_input(job_text)
            if not ok:
                st.error(f"Invalid job description: {reason}")
            else:
                sanitized = extractor.sanitize_input(job_text)
                try:
                    with st.spinner("Parsing job description and extracting skills..."):
                        extracted = extractor.extract(sanitized)
                    st.session_state.extracted_skills = extracted
                except Exception as exc:
                    st.error(f"Failed to extract skills from the job description: {str(exc)}")
                    st.session_state.quiz_generated = False
                    st.session_state.extracted_skills = None
                    return

                if st.session_state.extracted_skills:
                    try:
                        qgen = SkillQuestionGenerator(provider=provider)
                        with st.spinner("Generating skill-matched quiz questions..."):
                            questions, alignment = qgen.generate_questions(
                                st.session_state.extracted_skills,
                                question_type,
                                difficulty,
                                num_questions,
                            )
                        st.session_state.quiz_manager.set_questions(questions)
                        st.session_state.quiz_generated = True
                        st.session_state.job_alignment_report = alignment
                    except Exception as exc:
                        st.error(f"Failed to generate skill-matched questions: {str(exc)}")
                        st.session_state.quiz_generated = False
                        st.session_state.job_alignment_report = None
                        return
                rerun()

    # --- MAIN VIEW ENHANCEMENTS ---
    if mode == "Job Description Quiz":
        # 1. Candidate Profiling and Radar Diagnostic
        _render_candidate_matcher(job_text, provider=provider)
        
        # 2. Visual Analytics for Extracted JD Skills
        if st.session_state.extracted_skills is not None:
            _render_skill_preview(st.session_state.extracted_skills)

    # --- QUIZ INTERACTION & EVALUATION (100% Retained) ---
    if st.session_state.quiz_generated and st.session_state.quiz_manager.questions:
        st.header("Quiz")
        st.session_state.quiz_manager.attempt_quiz()

        if st.button("Submit Quiz"):
            st.session_state.quiz_manager.evaluate_quiz()
            st.session_state.quiz_submitted = True
            rerun()

    if st.session_state.quiz_submitted:
        st.header("Quiz Results")
        results_df = st.session_state.quiz_manager.generate_result_dataframe()

        if not results_df.empty:
            correct_count = results_df["is_correct"].sum()
            total_questions = len(results_df)
            score_percentage = round((correct_count / total_questions) * 100, 1)
            st.write(f"Score : {score_percentage}%")

            for _, result in results_df.iterrows():
                question_num = result["question_number"]
                target_skill = result.get("target_skill")
                if result["is_correct"]:
                    header = f"✅ Question {question_num}"
                    if target_skill:
                        header += f"  _[{target_skill}]_"
                    st.success(f"{header} : {result['question']}")
                    st.write(f"**Your answer:** {result['user_answer']}")
                else:
                    header = f"❌ Question {question_num}"
                    if target_skill:
                        header += f"  _[{target_skill}]_"
                    st.error(f"{header} : {result['question']}")
                    st.write(f"Your answer : {result['user_answer']}")
                    st.write(f"Correct answer : {result['correct_answer']}")

                # Show the explanation for every question, correct or not.
                explanation = result.get("explanation")
                if explanation:
                    st.info(f"💡 Explanation: {explanation}")

                st.markdown("-------")

            if mode == "Job Description Quiz":
                _render_alignment_report(st.session_state.job_alignment_report)

            if st.button("Save Results"):
                saved_file = st.session_state.quiz_manager.save_to_csv()
                if saved_file:
                    st.session_state.saved_results_file = saved_file
                else:
                    st.warning("No results available")

            saved_file = st.session_state.get("saved_results_file")
            if saved_file and os.path.exists(saved_file):
                with open(saved_file, "rb") as f:
                    st.download_button(
                        label="Download Results",
                        data=f.read(),
                        file_name=os.path.basename(saved_file),
                        mime="text/csv",
                    )


if __name__ == "__main__":
    main()