from langchain_openai import ChatOpenAI
from src.config.settings import settings


def get_deepseek_llm():
    """
    Builds a DeepSeek chat model client.

    DeepSeek exposes an OpenAI-compatible API, so we reuse ChatOpenAI and only
    override the base_url. Configuration is fully independent from the Groq
    client: it reads its own API key, model name, and endpoint from settings.
    """
    api_key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not configured. Add it to your .env file "
            "(DEEPSEEK_API_KEY=sk-...) or select the Groq provider instead."
        )

    return ChatOpenAI(
        api_key=api_key,
        model=settings.DEEPSEEK_MODEL_NAME,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=settings.TEMPERATURE,
    )
