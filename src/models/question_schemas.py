from typing import List
from pydantic import BaseModel,Field,validator

class MCQQuestion(BaseModel):

    question: str = Field(description="The question text")

    options: List[str] = Field(description="List of 4 options")

    correct_answer: str = Field(description="The correct answer from the options")

    explanation: str = Field(
        default="",
        description="A concise explanation of why the correct answer is right (shown for every question, correct or not)",
    )

    @validator('question' , pre=True)
    def clean_question(cls,v):
        if isinstance(v,dict):
            return v.get('description' , str(v))
        return str(v)
    

class FillBlankQuestion(BaseModel):

    question: str = Field(description="The question text with '___' for the blank")

    answer : str = Field(description="The correct word or phrase for the blank")

    explanation: str = Field(
        default="",
        description="A concise explanation of why the answer is right (shown for every question, correct or not)",
    )

    @validator('question' , pre=True)
    def clean_question(cls,v):
        if isinstance(v,dict):
            return v.get('description' , str(v))
        return str(v)


class SkillTaggedMCQQuestion(BaseModel):

    question: str = Field(description="The question text")

    options: List[str] = Field(description="List of exactly 4 options")

    correct_answer: str = Field(description="The correct answer from the options list")

    target_skill: str = Field(description="The exact skill name (from the extracted skill list) that this question assesses")

    explanation: str = Field(
        default="",
        description="A concise explanation of why the correct answer is right (shown for every question, correct or not)",
    )

    @validator('question', pre=True)
    def clean_question(cls, v):
        if isinstance(v, dict):
            return v.get('description', str(v))
        return str(v)


class SkillTaggedFillBlankQuestion(BaseModel):

    question: str = Field(description="The question text with '___' marking the blank")

    answer: str = Field(description="The correct word or phrase for the blank")

    target_skill: str = Field(description="The exact skill name (from the extracted skill list) that this question assesses")

    explanation: str = Field(
        default="",
        description="A concise explanation of why the answer is right (shown for every question, correct or not)",
    )

    @validator('question', pre=True)
    def clean_question(cls, v):
        if isinstance(v, dict):
            return v.get('description', str(v))
        return str(v)