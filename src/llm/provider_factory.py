"""
LLM provider factory.

Single dispatch point that returns a LangChain chat model for the requested
provider. The two provider branches are fully independent: each one imports
only its own client module, reads only its own settings, and neither branch
references the other. Adding a new provider means adding one branch here plus
one client module -- no changes to any consumer.
"""

from src.llm.groq_client import get_groq_llm

SUPPORTED_PROVIDERS = ("groq", "deepseek")

DEFAULT_PROVIDER = "groq"


def get_llm(provider: str = DEFAULT_PROVIDER):
    """
    Returns a LangChain chat model instance for the given provider.

    Args:
        provider: Provider identifier, case-insensitive. One of SUPPORTED_PROVIDERS.

    Returns:
        A LangChain BaseChatModel exposing the standard .invoke() interface.

    Raises:
        ValueError: If the provider is not supported.
    """
    key = str(provider or DEFAULT_PROVIDER).strip().lower()

    if key == "groq":
        return get_groq_llm()

    if key == "deepseek":
        # Imported lazily so that a missing DeepSeek dependency or key never
        # affects the Groq code path.
        from src.llm.deepseek_client import get_deepseek_llm

        return get_deepseek_llm()

    raise ValueError(
        f"Unsupported LLM provider: '{provider}'. "
        f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}."
    )
