"""
LLM client factory/router.

Supported providers:
- deepseek: uses DeepSeekClient (OpenAI-compatible)
- openrouter: uses OpenRouterClient (OpenAI-compatible), default model is Gemini Flash Lite
"""

from __future__ import annotations

from typing import Any, Protocol

from src.config import config


class LLMClient(Protocol):
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> dict[str, Any]: ...

    def get_usage_stats(self) -> dict[str, int]: ...
    def reset_usage_stats(self) -> None: ...


_client: LLMClient | None = None
_provider: str | None = None


def llm() -> LLMClient:
    global _client, _provider

    provider = (config.LLM_PROVIDER or "openrouter").strip().lower()
    if _client is not None and _provider == provider:
        return _client

    if provider == "deepseek":
        from .deepseek_client import DeepSeekClient

        _client = DeepSeekClient()
    elif provider == "openrouter":
        from .openrouter_client import OpenRouterClient

        _client = OpenRouterClient()
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER='{provider}'. Use 'deepseek' or 'openrouter'.")

    _provider = provider
    return _client
