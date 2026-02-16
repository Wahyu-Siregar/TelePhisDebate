"""
DeepSeek API client with retry logic and token tracking
"""

import json
import time
from typing import Any
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config


class DeepSeekClient:
    """Wrapper for DeepSeek API with error handling and retry logic"""
    
    def __init__(self):
        if not config.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY must be set in environment")
        
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL
        )

        # Token usage tracking
        self.total_tokens_input = 0
        self.total_tokens_output = 0
        self.request_count = 0
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> dict[str, Any]:
        """
        Send chat completion request to DeepSeek.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            json_mode: If True, request JSON response format
            
        Returns:
            Dict with 'content', 'tokens_input', 'tokens_output'
        """
        start_time = time.time()
        
        kwargs = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = self.client.chat.completions.create(**kwargs)
        
        # Track token usage
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        self.total_tokens_input += tokens_in
        self.total_tokens_output += tokens_out
        self.request_count += 1
        
        content = response.choices[0].message.content
        
        # Parse JSON if json_mode
        if json_mode:
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass  # Return raw string if parsing fails
        
        return {
            "content": content,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }
    
    def get_usage_stats(self) -> dict[str, int]:
        """Get current session token usage statistics"""
        return {
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_tokens": self.total_tokens_input + self.total_tokens_output,
            "request_count": self.request_count
        }
    
    def reset_usage_stats(self):
        """Reset token usage counters"""
        self.total_tokens_input = 0
        self.total_tokens_output = 0
        self.request_count = 0


# Singleton instance
_deepseek_client: DeepSeekClient | None = None


def deepseek() -> DeepSeekClient:
    """Get or create DeepSeek client singleton"""
    global _deepseek_client
    
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
    
    return _deepseek_client
