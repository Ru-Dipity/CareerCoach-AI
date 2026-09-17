import json
from typing import Optional

from src.llm.provider_factory import get_llm
from src.prompts.templates import candidate_job_match_prompt_template
from src.models.matching_schemas import MatchResult
from src.common.custom_exception import CustomException
from src.common.logger import get_logger


class ProfileJobMatcher:
    """
    Evaluates candidate profile against job specifications using LLM reasoning.
    """

    def __init__(self, llm_client=None, provider: str = "groq"):
        self.client = llm_client or get_llm(provider)
        self.logger = get_logger(self.__class__.__name__)

    def analyze_match(self, job_description: str, candidate_profile: str) -> MatchResult:
        """
        Calculates alignment metrics, dimension scores, and gap analysis.
        """
        try:
            from langchain_core.output_parsers import PydanticOutputParser

            parser = PydanticOutputParser(pydantic_object=MatchResult)
            prompt = candidate_job_match_prompt_template.format(
                job_text=job_description.strip(),
                candidate_text=candidate_profile.strip(),
                format_instructions=parser.get_format_instructions(),
            )

            self.logger.info("Initiating candidate-job alignment analysis with LLM...")
            response = self.client.invoke(prompt)
            raw_response = response.content if hasattr(response, "content") else str(response)

            # Strip code blocks if returned by the LLM
            clean_json_str = raw_response.strip()
            if clean_json_str.startswith("```json"):
                clean_json_str = clean_json_str[7:]
            if clean_json_str.startswith("```"):
                clean_json_str = clean_json_str[3:]
            if clean_json_str.endswith("```"):
                clean_json_str = clean_json_str[:-3]

            parsed_data = json.loads(clean_json_str.strip())
            result = MatchResult(**parsed_data)

            self.logger.info(f"Analysis completed successfully. Overall Match Score: {result.overall_score}%")
            return result

        except Exception as e:
            self.logger.error(f"Failed to generate match analysis: {str(e)}")
            raise CustomException("Match evaluation encountered an error", e)
