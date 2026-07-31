from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base_provider import BaseAIProvider
from app.ai.caching_provider import CachingAIProvider
from app.ai.fake_provider import FakeAIProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings

settings = get_settings()


def get_ai_provider() -> BaseAIProvider:
    """Selects the AI backend based on AI_PROVIDER (see .env.example).
    Defaults to the fake provider so the app runs out of the box with no
    API keys - set AI_PROVIDER=anthropic|openai plus the matching *_API_KEY
    for real interviews. Real providers get wrapped with question caching;
    the fake one is already instant, so caching it would add nothing."""
    if settings.AI_PROVIDER == "anthropic":
        return CachingAIProvider(AnthropicProvider())
    if settings.AI_PROVIDER == "openai":
        return CachingAIProvider(OpenAIProvider())
    if settings.AI_PROVIDER == "fake":
        return FakeAIProvider()
    raise RuntimeError(f"Unknown AI_PROVIDER: {settings.AI_PROVIDER!r}")
