from typing import List, Optional
from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    dimension: str = Field(
        description="Dimension category (e.g., Backend Engineering, Cloud & DevOps, System Design, Data Architecture, Collaboration)"
    )
    job_requirement: float = Field(
        description="Target score required by the job on a scale of 0 to 100",
        ge=0,
        le=100,
    )
    candidate_capability: float = Field(
        description="Assessed score of the candidate on a scale of 0 to 100",
        ge=0,
        le=100,
    )


class SkillItem(BaseModel):
    name: str = Field(description="Skill or tool name, e.g., Python, Kubernetes")
    category: str = Field(description="Skill category, e.g., Cloud/DevOps, Database, Backend")
    weight: int = Field(description="Relative importance score from 1 to 5", ge=1, le=5)
    is_required: bool = Field(description="True if mandatory (Must-have), False if optional (Nice-to-have)")


class MatchResult(BaseModel):
    overall_score: int = Field(
        description="Overall match percentage between candidate and JD (0-100)",
        ge=0,
        le=100,
    )
    radar_data: List[DimensionScore] = Field(
        description="Multidimensional breakdown for radar chart visualization"
    )
    matched_skills: List[str] = Field(
        description="Key skills and qualifications satisfied by the candidate"
    )
    missing_skills: List[str] = Field(
        description="Skills required by the job that are missing or insufficiently represented in candidate profile"
    )
    strengths: List[str] = Field(
        description="Key highlights where the candidate matches or exceeds job requirements"
    )
    gap_analysis: List[str] = Field(
        description="Key areas where development or clarification is needed"
    )
    targeted_interview_topics: List[str] = Field(
        description="Recommended interview discussion points or challenge areas to verify candidate competence"
    )