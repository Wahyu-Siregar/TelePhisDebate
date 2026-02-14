"""
LLM module - DeepSeek API wrapper and utilities
"""

from .factory import llm


def deepseek():
    """
    Backward-compatible alias.

    Historically, the code imported `deepseek()` everywhere.
    Now it routes to the configured provider via LLM_PROVIDER.
    """
    return llm()

__all__ = ["deepseek", "llm"]
