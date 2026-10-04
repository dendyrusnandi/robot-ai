from typing import Any

from providers.gemini_live import GeminiLiveProvider
from providers.mock_provider import MockRealtimeProvider
from providers.openai_realtime import OpenAIRealtimeProvider


def create_provider(config: dict[str, Any]):
    provider = config["ai"]["provider"]
    if provider == "gemini":
        return GeminiLiveProvider(config)
    if provider == "openai":
        return OpenAIRealtimeProvider(config)
    if provider == "mock":
        return MockRealtimeProvider(config)
    raise ValueError(f"Unknown AI provider: {provider}")

