"""
LLM module - DeepSeek API wrapper and utilities
"""

from .deepseek_client import DeepSeekClient
from .factory import llm


def deepseek():
    """
    Backward-compatible alias.

    Historically, the code imported `deepseek()` everywhere.
    It now routes to the configured provider via LLM_PROVIDER:
    - openrouter (default)
    - deepseek
    """
    return llm()

__all__ = ["DeepSeekClient", "deepseek", "llm"]
