import json
import re
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from src.llm.provider_factory import get_llm
from src.config.settings import settings
from src.common.logger import get_logger
from src.common.custom_exception import CustomException

# Retained for backward-compatibility with external imports
CANONICAL_CATEGORIES: List[str] = []

# Refined prompt injection detection to avoid falsely flagging non-IT professions
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(previous|all|above|prior)\b"),
    re.compile(r"(?i)\bsystem\s+prompt\b"),
    re.compile(r"(?i)<\s*\|?(?:assistant|system|user|human)\|?\s*>"),
    re.compile(r"(?i)\bdisregard\s+(instructions|context|rules)\b"),
    re.compile(r"(?i)\b(jailbreak|DAN\s+mode|unrestricted\s+mode)\b"),
]

# Cross-industry normalization alias mapping
_SKILL_NORMALIZATION_MAP = {
    # Tech / Cloud / DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "gcp": "GCP",
    "google cloud platform": "GCP",
    "k8s": "Kubernetes",
    "kubernates": "Kubernetes",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ci cd": "CI/CD",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "node": "Node.js",
    "nodejs": "Node.js",
    "reactjs": "React",
    "sql database": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "docker container": "Docker",
    # Sales, Marketing & Business
    "sales force": "Salesforce",
    "crm": "CRM",
    "hubspot": "HubSpot",
    "seo": "SEO",
    "sem": "SEM",
    "b2b": "B2B",
    "b2c": "B2C",
    "saas": "SaaS",
    # Finance, Accounting & Compliance
    "gaap": "GAAP",
    "ifrs": "IFRS",
    "cpa": "CPA",
    "cfa": "CFA",
    "aml": "AML",
    "kyc": "KYC",
    # Healthcare & Clinical
    "hipaa": "HIPAA",
    "bls": "BLS",
    "acls": "ACLS",
    "emr": "EMR",
    "ehr": "EHR",
    # Operations & HR
    "erp": "ERP",
    "kpi": "KPI",
    "kpis": "KPIs",
    "okr": "OKR",
    "okrs": "OKRs",
    "hris": "HRIS",
}

# Industry acronyms that should remain capitalized
_KNOWN_UPPERCASE_ACRONYMS = {
    "AWS", "GCP", "CI/CD", "CRM", "B2B", "B2C", "SaaS", "SQL", "ERP",
    "KPI", "KPIS", "OKR", "OKRS", "HRIS", "GAAP", "IFRS", "CPA", "CFA",
    "AML", "KYC", "HIPAA", "BLS", "ACLS", "EMR", "EHR", "SEO", "SEM",
    "PR", "ROI", "P&L", "CAD", "GIS", "UI", "UX", "API", "APIS", "AI", "ML"
}


class JobSkill(BaseModel):
    skill_name: str = Field(description="Normalized skill or competency name in consistent casing")
    category: str = Field(description="Dynamic, role-relevant domain category assigned by the model")
    occurrence_count: int = Field(description="Number of times the skill/competency was mentioned", ge=1)


class ExtractedSkills(BaseModel):
    role_title: Optional[str] = Field(
        default=None, description="Detected job title across any industry (e.g. 'Senior Financial Analyst', 'ICU Registered Nurse')"
    )
    seniority: Optional[str] = Field(
        default=None,
        description="Detected seniority level (e.g. Intern, Junior, Mid, Senior, Lead, Director, Head, VP, Partner)",
    )
    skills: List[JobSkill] = Field(description="List of extracted, deduplicated, and categorized domain skills")


class SkillExtractor:
    def __init__(self, provider: str = "groq"):
        self.llm = get_llm(provider)
        self.logger = get_logger(self.__class__.__name__)

    @staticmethod
    def validate_input(job_text: str) -> Tuple[bool, str]:
        if job_text is None or not str(job_text).strip():
            return False, "Job description cannot be empty."
        text = str(job_text)
        if len(text) > settings.MAX_JOB_TEXT_LENGTH:
            return False, (
                f"Job description exceeds the maximum allowed length of "
                f"{settings.MAX_JOB_TEXT_LENGTH} characters (got {len(text)})."
            )
        for pattern in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                return False, "Input contains disallowed override patterns (possible prompt injection attempt)."
        return True, "OK"

    @staticmethod
    def sanitize_input(job_text: str) -> str:
        text = str(job_text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        preserved = []
        for ch in text:
            cp = ord(ch)
            if ch in ("\n", "\t") or cp >= 0x20:
                preserved.append(ch)
        cleaned = "".join(preserved)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def _normalize_skill_name(name: str) -> str:
        key = name.strip().lower()
        if key in _SKILL_NORMALIZATION_MAP:
            return _SKILL_NORMALIZATION_MAP[key]
        tokens = re.split(r"\s+", name.strip())
        if not tokens:
            return name.strip()
        
        joined_lower = " ".join([t.lower() for t in tokens])
        if joined_lower in _SKILL_NORMALIZATION_MAP:
            return _SKILL_NORMALIZATION_MAP[joined_lower]

        # Single uppercase acronym recognition (e.g., CPA, ICU, CNC)
        if len(tokens) == 1 and len(tokens[0]) <= 5 and tokens[0].upper() == tokens[0]:
            return tokens[0]

        small_words = {"and", "or", "the", "for", "with", "of", "in", "on", "to", "vs", "via", "&"}
        result = []
        for tok in tokens:
            if not tok:
                continue
            lo = tok.lower()
            up = tok.upper()
            if up in _KNOWN_UPPERCASE_ACRONYMS:
                result.append(up)
            elif lo in small_words:
                result.append(lo)
            else:
                result.append(tok[0].upper() + tok[1:].lower())
        return " ".join(result)

    @staticmethod
    def _normalize_category(category: Optional[str]) -> str:
        """Standardizes category text from LLM across any domain."""
        if not category or not category.strip():
            return "General Competencies"
        cat = category.strip().strip("\"'[]")
        tokens = [
            w.capitalize() if w.lower() not in {"and", "&", "or", "of", "in"} else w.lower()
            for w in cat.split()
        ]
        formatted = " ".join(tokens)
        return formatted if formatted else "General Competencies"

    def _post_process(self, extracted: ExtractedSkills) -> ExtractedSkills:
        seen = {}
        ordered = []
        for skill in extracted.skills:
            norm_name = self._normalize_skill_name(skill.skill_name)
            key = norm_name.lower()
            cat = self._normalize_category(skill.category)
            count = max(1, int(getattr(skill, "occurrence_count", 1) or 1))
            if key in seen:
                idx = seen[key]
                existing = ordered[idx]
                existing["occurrence_count"] += count
                if existing["category"] == "General Competencies" and cat != "General Competencies":
                    existing["category"] = cat
            else:
                seen[key] = len(ordered)
                ordered.append({
                    "skill_name": norm_name,
                    "category": cat,
                    "occurrence_count": count,
                })
        ordered.sort(key=lambda s: (-s["occurrence_count"], s["skill_name"].lower()))
        extracted.skills = [JobSkill(**row) for row in ordered]
        
        if extracted.role_title:
            extracted.role_title = extracted.role_title.strip() or None

        # Cross-industry seniority detection hierarchy
        if extracted.seniority:
            seniority_candidates = [
                "Partner", "Managing Director", "Director", "Vice President", "VP",
                "Head", "Principal", "Staff", "Senior", "Lead", "Manager",
                "Mid", "Associate", "Junior", "Intern", "Entry"
            ]
            raw = extracted.seniority.strip()
            matched = None
            for cand in seniority_candidates:
                if cand.lower() in raw.lower():
                    matched = cand
                    break
            extracted.seniority = matched or (raw or None)
        return extracted

    def _retry_and_parse(self, prompt: PromptTemplate, parser: PydanticOutputParser, job_text: str) -> ExtractedSkills:
        for attempt in range(settings.MAX_RETRIES):
            try:
                self.logger.info(f"Extracting domain skills from job description (attempt {attempt + 1}/{settings.MAX_RETRIES})")
                fmt = parser.get_format_instructions()
                response = self.llm.invoke(prompt.format(job_text=job_text, format_instructions=fmt))
                parsed = parser.parse(response.content)
                self.logger.info("Successfully parsed domain skills")
                return parsed
            except Exception as e:
                self.logger.error(f"Domain extraction attempt {attempt + 1} failed: {str(e)}")
                if attempt == settings.MAX_RETRIES - 1:
                    raise CustomException(f"Domain extraction failed after {settings.MAX_RETRIES} attempts", e)
        raise CustomException("Skill extraction failed: retry loop exhausted", None)

    def extract(self, job_text: str) -> ExtractedSkills:
        from src.prompts.templates import skill_extraction_prompt_template

        try:
            parser = PydanticOutputParser(pydantic_object=ExtractedSkills)
            raw = self._retry_and_parse(skill_extraction_prompt_template, parser, job_text)
            cleaned = self._post_process(raw)
            if not cleaned.skills:
                raise ValueError("No skills or competencies were extracted from the job description.")
            self.logger.info(f"Extracted {len(cleaned.skills)} unique competencies")
            return cleaned
        except Exception as e:
            self.logger.error(f"Failed to extract skills: {str(e)}")
            raise CustomException("Skill extraction failed", e)


def compute_alignment(questions: list, extracted: ExtractedSkills) -> dict:
    if not extracted or not extracted.skills:
        return {"aligned": 0, "total": len(questions), "ratio": 0.0, "unmapped": []}
    normalized = {s.skill_name.lower() for s in extracted.skills}
    aliases = {}
    for s in extracted.skills:
        aliases[s.skill_name.lower()] = s.skill_name
        key = s.skill_name.lower().replace(" ", "").replace("/", "").replace("-", "")
        aliases[key] = s.skill_name
    total = len(questions)
    aligned = 0
    unmapped = []
    for idx, q in enumerate(questions):
        target = str(q.get("target_skill", "") if isinstance(q, dict) else getattr(q, "target_skill", ""))
        if not target:
            unmapped.append({
                "index": idx,
                "target_skill": "",
                "question": q.get("question", "")[:60] if isinstance(q, dict) else "",
            })
            continue
        t_lo = target.lower().strip()
        direct = t_lo in normalized
        collapsed = t_lo.replace(" ", "").replace("/", "").replace("-", "") in aliases
        if direct or collapsed:
            aligned += 1
        else:
            snippet = q.get("question", "")[:60] if isinstance(q, dict) else getattr(q, "question", "")[:60]
            unmapped.append({"index": idx, "target_skill": target, "question": snippet})
    ratio = (aligned / total) if total else 0.0
    return {"aligned": aligned, "total": total, "ratio": round(ratio, 4), "unmapped": unmapped}


class SkillQuestionGenerator:
    def __init__(self, provider: str = "groq"):
        self.llm = get_llm(provider)
        self.logger = get_logger(self.__class__.__name__)

    @staticmethod
    def _skill_list_to_json(extracted: ExtractedSkills) -> str:
        payload = [
            {
                "skill_name": s.skill_name,
                "category": s.category,
                "occurrence_count": s.occurrence_count,
            }
            for s in extracted.skills
        ]
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _retry_and_parse_mcq(self, role_title, seniority, difficulty, skill_list_json) -> "SkillTaggedMCQQuestion":
        from src.prompts.templates import job_skill_mcq_prompt_template
        from src.models.question_schemas import SkillTaggedMCQQuestion

        parser = PydanticOutputParser(pydantic_object=SkillTaggedMCQQuestion)
        fmt = parser.get_format_instructions()
        for attempt in range(settings.MAX_RETRIES):
            try:
                self.logger.info(
                    f"Generating skill-tagged MCQ (difficulty={difficulty}, attempt {attempt + 1}/{settings.MAX_RETRIES})"
                )
                response = self.llm.invoke(
                    job_skill_mcq_prompt_template.format(
                        role_title=role_title or "",
                        seniority=seniority or "",
                        difficulty=difficulty,
                        skill_list_json=skill_list_json,
                        format_instructions=fmt,
                    )
                )
                parsed = parser.parse(response.content)
                if len(parsed.options) != 4 or parsed.correct_answer not in parsed.options:
                    raise ValueError(
                        "SkillTaggedMCQ failed structural validation (4 options required, correct_answer in options)"
                    )
                if not parsed.target_skill or not str(parsed.target_skill).strip():
                    raise ValueError("SkillTaggedMCQ missing required target_skill field")
                self.logger.info("Successfully parsed skill-tagged MCQ")
                return parsed
            except Exception as e:
                self.logger.error(f"Skill MCQ attempt {attempt + 1} failed: {str(e)}")
                if attempt == settings.MAX_RETRIES - 1:
                    raise CustomException(f"Skill MCQ generation failed after {settings.MAX_RETRIES} attempts", e)
        raise CustomException("Skill MCQ generation failed: retry loop exhausted", None)

    def _retry_and_parse_fillblank(self, role_title, seniority, difficulty, skill_list_json) -> "SkillTaggedFillBlankQuestion":
        from src.prompts.templates import job_skill_fillblank_prompt_template
        from src.models.question_schemas import SkillTaggedFillBlankQuestion

        parser = PydanticOutputParser(pydantic_object=SkillTaggedFillBlankQuestion)
        fmt = parser.get_format_instructions()
        for attempt in range(settings.MAX_RETRIES):
            try:
                self.logger.info(
                    f"Generating skill-tagged FillBlank (difficulty={difficulty}, attempt {attempt + 1}/{settings.MAX_RETRIES})"
                )
                response = self.llm.invoke(
                    job_skill_fillblank_prompt_template.format(
                        role_title=role_title or "",
                        seniority=seniority or "",
                        difficulty=difficulty,
                        skill_list_json=skill_list_json,
                        format_instructions=fmt,
                    )
                )
                parsed = parser.parse(response.content)
                if "___" not in parsed.question:
                    raise ValueError("SkillTaggedFillBlank must contain '___' in the question")
                if not parsed.target_skill or not str(parsed.target_skill).strip():
                    raise ValueError("SkillTaggedFillBlank missing required target_skill field")
                self.logger.info("Successfully parsed skill-tagged FillBlank")
                return parsed
            except Exception as e:
                self.logger.error(f"Skill FillBlank attempt {attempt + 1} failed: {str(e)}")
                if attempt == settings.MAX_RETRIES - 1:
                    raise CustomException(f"Skill FillBlank generation failed after {settings.MAX_RETRIES} attempts", e)
        raise CustomException("Skill FillBlank generation failed: retry loop exhausted", None)

    def generate_questions(
        self,
        extracted: ExtractedSkills,
        question_type: str,
        difficulty: str,
        num_questions: int,
    ) -> list:
        if extracted is None or not extracted.skills:
            raise ValueError("Cannot generate questions: extracted skills list is empty.")
        difficulty_norm = str(difficulty).strip().lower() or "medium"
        skill_list_json = self._skill_list_to_json(extracted)
        questions_raw = []
        for _ in range(num_questions):
            if question_type == "Multiple Choice":
                q = self._retry_and_parse_mcq(
                    extracted.role_title, extracted.seniority, difficulty_norm, skill_list_json
                )
                questions_raw.append({
                    "type": "MCQ",
                    "question": q.question,
                    "options": list(q.options),
                    "correct_answer": q.correct_answer,
                    "target_skill": q.target_skill,
                    "explanation": getattr(q, "explanation", "") or "",
                })
            else:
                q = self._retry_and_parse_fillblank(
                    extracted.role_title, extracted.seniority, difficulty_norm, skill_list_json
                )
                questions_raw.append({
                    "type": "Fill in the blank",
                    "question": q.question,
                    "correct_answer": q.answer,
                    "target_skill": q.target_skill,
                    "explanation": getattr(q, "explanation", "") or "",
                })
        alignment = compute_alignment(questions_raw, extracted)
        self.logger.info(
            f"Generated {len(questions_raw)} skill-matched questions "
            f"(aligned={alignment['aligned']}/{alignment['total']}, ratio={alignment['ratio']})"
        )
        return questions_raw, alignment