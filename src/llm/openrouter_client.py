"""
OpenRouter client (OpenAI-compatible) with retry logic and token tracking.

This is used to run GPT-OSS free model for comparison against deepseek-chat.
"""

import json
import re
import time
from collections import deque
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from tenacity.retry import retry_if_exception

from src.config import config


def _is_transient_openrouter_error(exc: Exception) -> bool:
    """
    Retry only on transient errors.

    We avoid retrying on errors that are almost always configuration/model problems
    (e.g., NotFoundError for unknown model, AuthenticationError for bad key).
    """
    name = exc.__class__.__name__
    if name in {
        "NotFoundError",
        "AuthenticationError",
        "PermissionDeniedError",
        "BadRequestError",
        "UnprocessableEntityError",
    }:
        return False
    return True


class OpenRouterClient:
    def __init__(self):
        if not config.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY must be set when LLM_PROVIDER=openrouter")

        headers: dict[str, str] = {}
        if config.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = config.OPENROUTER_SITE_URL
        if config.OPENROUTER_APP_NAME:
            headers["X-Title"] = config.OPENROUTER_APP_NAME

        kwargs: dict[str, Any] = {
            "api_key": config.OPENROUTER_API_KEY,
            "base_url": config.OPENROUTER_BASE_URL,
        }
        if headers:
            kwargs["default_headers"] = headers

        self.client = OpenAI(**kwargs)

        self.total_tokens_input = 0
        self.total_tokens_output = 0
        self.request_count = 0
        self._rpm = int(getattr(config, "OPENROUTER_MAX_RPM", 0) or 0)
        # Track request timestamps to avoid bursting past free-tier RPM limits.
        self._req_ts: deque[float] = deque()

    def _throttle(self) -> None:
        """Best-effort client-side RPM throttling."""
        if self._rpm <= 0:
            return
        now = time.monotonic()
        window_s = 60.0
        # Drop old timestamps outside the window.
        while self._req_ts and (now - self._req_ts[0]) > window_s:
            self._req_ts.popleft()
        if len(self._req_ts) < self._rpm:
            return
        # Sleep until we are under the limit.
        sleep_s = window_s - (now - self._req_ts[0]) + 0.05
        if sleep_s > 0:
            time.sleep(sleep_s)
        # After sleeping, drop old timestamps.
        now2 = time.monotonic()
        while self._req_ts and (now2 - self._req_ts[0]) > window_s:
            self._req_ts.popleft()

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(_is_transient_openrouter_error),
        reraise=True,
    )
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        start_time = time.time()

        # Some OpenRouter-hosted models are more likely to follow strict JSON formatting at low temperature.
        if json_mode:
            temperature = min(float(temperature or 0.0), 0.2)

        # Avoid bursty parallel calls (MAD3 uses 3 agents) by throttling per-process.
        self._throttle()

        kwargs: dict[str, Any] = {
            "model": config.OPENROUTER_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            # OpenAI-compatible servers may or may not honor this, but it doesn't hurt.
            kwargs["response_format"] = {"type": "json_object"}

        # Track timestamp as "request attempted" to smooth bursts even if it errors.
        self._req_ts.append(time.monotonic())

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Special handling for 429: OpenRouter returns helpful rate limit reset headers in error payload.
            s = str(exc)
            if "Error code: 429" in s or "Rate limit exceeded" in s:
                m = re.search(r"X-RateLimit-Reset'\s*:\s*'(\d+)'", s)
                if m:
                    try:
                        reset_ms = int(m.group(1))
                        sleep_s = max(0.0, (reset_ms / 1000.0) - time.time()) + 0.25
                        if sleep_s > 0:
                            time.sleep(sleep_s)
                    except Exception:
                        # Fall back to tenacity exponential wait.
                        pass
            raise

        usage = getattr(response, "usage", None)
        if usage is None:
            # Some providers don't populate `response.usage` but may include it in the raw dict.
            try:
                raw = response.model_dump()  # type: ignore[attr-defined]
                usage = raw.get("usage")
            except Exception:
                usage = None

        if isinstance(usage, dict):
            tokens_in = int(usage.get("prompt_tokens", 0) or 0)
            tokens_out = int(usage.get("completion_tokens", 0) or 0)
        else:
            tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
            tokens_out = int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0

        self.total_tokens_input += tokens_in
        self.total_tokens_output += tokens_out
        self.request_count += 1

        content = response.choices[0].message.content
        raw_text = content
        if json_mode:
            try:
                content = json.loads(content)
            except Exception:
                pass

        return {
            "content": content,
            "raw_content": raw_text,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }

    def get_usage_stats(self) -> dict[str, int]:
        return {
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_tokens": self.total_tokens_input + self.total_tokens_output,
            "request_count": self.request_count,
        }

    def reset_usage_stats(self):
        self.total_tokens_input = 0
        self.total_tokens_output = 0
        self.request_count = 0
