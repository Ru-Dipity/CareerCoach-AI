from langchain_core.prompts import PromptTemplate

# ==========================================
# 1. Baseline Single-Topic Quiz Templates
# ==========================================

mcq_prompt_template = PromptTemplate(
    template=(
        "Generate a {difficulty} multiple-choice question about {topic}.\n\n"
        "Return ONLY a JSON object with these exact fields:\n"
        "- 'question': A clear, specific question\n"
        "- 'options': An array of exactly 4 possible answers\n"
        "- 'correct_answer': One of the options that is the correct answer\n"
        "- 'explanation': A concise explanation (1-3 sentences) of why the correct answer is right and why the other options are wrong\n\n"
        "Example format:\n"
        "{{\n"
        '    "question": "What is the capital of France?",\n'
        '    "options": ["London", "Berlin", "Paris", "Madrid"],\n'
        '    "correct_answer": "Paris",\n'
        '    "explanation": "Paris is the capital of France. London is the UK, Berlin is Germany, and Madrid is Spain."\n'
        "}}\n\n"
        "Your response:"
    ),
    input_variables=["topic", "difficulty"],
)

fill_blank_prompt_template = PromptTemplate(
    template=(
        "Generate a {difficulty} fill-in-the-blank question about {topic}.\n\n"
        "Return ONLY a JSON object with these exact fields:\n"
        "- 'question': A sentence with '___' marking exactly where the blank should be (exactly 3 underscores)\n"
        "- 'answer': The correct word or phrase that belongs in the blank\n"
        "- 'explanation': A concise explanation (1-3 sentences) of why the answer is correct\n\n"
        "Example format:\n"
        "{{\n"
        '    "question": "The capital of France is ___.",\n'
        '    "answer": "Paris",\n'
        '    "explanation": "Paris is the capital and most populous city of France."\n'
        "}}\n\n"
        "Your response:"
    ),
    input_variables=["topic", "difficulty"],
)

# ==========================================
# 2. Skill Extraction from Job Posting
# ==========================================

skill_extraction_prompt_template = PromptTemplate(
    template=(
        "You are an expert talent evaluation specialist and recruiter extracting structured skills from a job posting.\n\n"
        "Instructions:\n"
        "1. Read the job description thoroughly and identify its primary domain/industry (e.g., Software Engineering, DevOps, Sales & Business Development, Human Resources, Finance, Healthcare).\n"
        "2. Dynamically establish 4 to 6 concise, highly relevant skill categories tailored specifically to this role.\n"
        "   - Examples for Sales: 'Prospecting & Outreach', 'CRM & Pipeline Management', 'Negotiation & Closing', 'Client Relationship', 'Soft Skills'.\n"
        "   - Examples for DevOps: 'Cloud & Infrastructure', 'CI/CD & Automation', 'Containers & Orchestration', 'Monitoring & Observability', 'Soft Skills'.\n"
        "   - Examples for Finance: 'Financial Modeling', 'Risk & Compliance', 'Accounting & Auditing', 'Reporting & BI Tools', 'Soft Skills'.\n"
        "3. Extract all explicit technical skills, domain methodologies, specialized platforms, software tools, and distinct interpersonal soft skills.\n"
        "4. Assign every extracted skill to EXACTLY ONE of your dynamically formulated categories from step 2.\n"
        "5. For each extracted skill, estimate occurrence_count as the number of times it or a close synonym appears in the posting.\n"
        "6. Do NOT invent skills that are not stated in the posting.\n"
        "7. Provide the best-guess role_title (e.g., 'Enterprise Account Executive', 'Senior DevOps Engineer') and seniority level (Junior, Mid, Senior, Lead, Staff, Principal, Intern, Entry). Leave as null if unclear.\n\n"
        "Formatting rules - obey the Pydantic format strictly:\n"
        "{format_instructions}\n\n"
        "IMPORTANT: Return ONLY the JSON object. No surrounding prose, no markdown fences, no commentary.\n\n"
        "=== Job posting text ===\n"
        "{job_text}\n"
        "=== End job posting text ===\n\n"
        "Your JSON response:"
    ),
    input_variables=["job_text", "format_instructions"],
)

# ==========================================
# 3. JD Skill-Targeted Quiz Templates
# ==========================================

job_skill_mcq_prompt_template = PromptTemplate(
    template=(
        "You are an expert technical interviewer generating exam questions from role requirements.\n\n"
        "Context:\n"
        "- Role title (if known): {role_title}\n"
        "- Seniority (if known): {seniority}\n"
        "- Difficulty level for the question: {difficulty}\n"
        "- Full list of required skills with categories (this is your ONLY allowed scope):\n"
        "{skill_list_json}\n\n"
        "Your task: Generate exactly ONE multiple-choice question that clearly targets ONE specific skill from the list above.\n\n"
        "Rules:\n"
        "1. The question MUST be directly relevant to at least one of the listed skills. Aim for a skill with a high occurrence_count when possible.\n"
        "2. Set target_skill to the exact skill_name from the list that your question is testing.\n"
        "3. Provide exactly 4 distinct, plausible options. The correct answer must be one of the 4.\n"
        "4. Make distractors realistic; do not make them obviously wrong.\n"
        "5. If difficulty is 'Easy', test terminology or basic facts. If 'Medium', test application or configuration. If 'Hard', test subtle behavior, debugging, or trade-offs.\n"
        "6. Set explanation to a concise (1-3 sentences) rationale for why the correct answer is right and, where useful, why the distractors are wrong.\n\n"
        "Output ONLY a JSON object matching this Pydantic schema:\n"
        "{format_instructions}\n\n"
        "Your JSON response:"
    ),
    input_variables=["role_title", "seniority", "difficulty", "skill_list_json", "format_instructions"],
)

job_skill_fillblank_prompt_template = PromptTemplate(
    template=(
        "You are an expert technical interviewer generating exam questions from role requirements.\n\n"
        "Context:\n"
        "- Role title (if known): {role_title}\n"
        "- Seniority (if known): {seniority}\n"
        "- Difficulty level for the question: {difficulty}\n"
        "- Full list of required skills with categories (this is your ONLY allowed scope):\n"
        "{skill_list_json}\n\n"
        "Your task: Generate exactly ONE fill-in-the-blank question that clearly targets ONE specific skill from the list above.\n\n"
        "Rules:\n"
        "1. The question MUST be directly relevant to at least one of the listed skills.\n"
        "2. Set target_skill to the exact skill_name from the list that your question is testing.\n"
        "3. The 'question' field MUST contain the literal substring '___' (exactly three underscores) marking the position of the blank.\n"
        "4. The 'answer' field must be the exact word or short phrase that belongs in the blank.\n"
        "5. If difficulty is 'Easy', test terminology. If 'Medium', test application concepts. If 'Hard', test nuanced behavior.\n"
        "6. Set explanation to a concise (1-3 sentences) rationale for why the answer is correct.\n\n"
        "Output ONLY a JSON object matching this Pydantic schema:\n"
        "{format_instructions}\n\n"
        "Your JSON response:"
    ),
    input_variables=["role_title", "seniority", "difficulty", "skill_list_json", "format_instructions"],
)

# ==========================================
# 4. Candidate vs. Job Description Matching Template
# ==========================================

candidate_job_match_prompt_template = PromptTemplate(
    template=(
        "You are an objective technical recruiter and assessment specialist.\n"
        "Evaluate how well the candidate's profile/resume matches the target job description.\n\n"
        "Evaluation Guidelines:\n"
        "1. Analyze explicit matches, partial matches, and missing qualifications.\n"
        "2. Generate multidimensional evaluation data across 5 distinct dimensions tailored to this role.\n"
        "3. Provide realistic, evidence-based scores (0-100) for both job requirement baseline and candidate capability.\n"
        "4. Identify actionable technical strengths and gaps.\n\n"
        "Formatting rules - obey the Pydantic format strictly:\n"
        "{format_instructions}\n\n"
        "IMPORTANT: Return ONLY the JSON object matching the schema. Do NOT include markdown code blocks (```json) or conversational preamble.\n\n"
        "=== Target Job Description ===\n"
        "{job_text}\n"
        "=== End Job Description ===\n\n"
        "=== Candidate Profile / Resume ===\n"
        "{candidate_text}\n"
        "=== End Candidate Profile ===\n\n"
        "Your JSON response:"
    ),
    input_variables=["job_text", "candidate_text", "format_instructions"],
)