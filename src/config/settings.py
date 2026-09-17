import os
from dotenv import load_dotenv

load_dotenv()

class Settings():

    # ---- Groq provider configuration (independent) ----
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b")

    # ---- DeepSeek provider configuration (independent) ----
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

    DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ---- Shared generation parameters ----
    TEMPERATURE = 0.9

    MAX_RETRIES = 3

    MAX_JOB_TEXT_LENGTH = 10000

settings = Settings()
