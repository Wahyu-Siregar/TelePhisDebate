"""
Gemini API client (Google Generative Language API) with retry logic and token tracking.

Implements the same interface as DeepSeekClient.chat_completion() so it can be used as a drop-in
replacement via LLM_PROVIDER=gemini.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        # Remove ```json ... ``` wrappers.
        t = t.replace("```json", "```", 1)
        t = t.strip()
        if t.startswith("```"):
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def _extract_json_object(text: str) -> dict[str, Any] | str:
    """
    Best-effort JSON parsing. Returns dict on success, else returns original string.
    """
    t = _strip_fences(text)
    if not t:
        return {}

    # Try direct JSON first.
    try:
        parsed = json.loads(t)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting the first {...} block.
    first = t.find("{")
    last = t.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = t[first : last + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return text


class GeminiClient:
    """Wrapper for Gemini generateContent API with basic retries and token tracking."""

    def __init__(self):
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set in environment when LLM_PROVIDER=gemini")

        self.api_key = config.GEMINI_API_KEY
        self.base_url = (config.GEMINI_BASE_URL or "https://generativelanguage.googleapis.com").rstrip("/")
        self.model = config.GEMINI_MODEL or "gemini-1.5-flash"

        self.total_tokens_input = 0
        self.total_tokens_output = 0
        self.request_count = 0

        self._client = httpx.Client(timeout=httpx.Timeout(60.0))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        start_time = time.time()

        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = (msg.get("role") or "user").strip().lower()
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(str(content))
                continue

            gemini_role = "user" if role == "user" else "model"
            contents.append({"role": gemini_role, "parts": [{"text": str(content)}]})

        payload: dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generation_config": {
                "temperature": float(temperature),
                "max_output_tokens": int(max_tokens),
            },
        }

        system_text = "\n\n".join([p for p in system_parts if p.strip()]) or None
        if system_text:
            payload["system_instruction"] = {"parts": [{"text": system_text}]}

        # Strong hint to return JSON only, plus server-side JSON mime type (if supported).
        if json_mode:
            payload["generation_config"]["response_mime_type"] = "application/json"

        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent"
        resp = self._client.post(url, params={"key": self.api_key}, json=payload)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates") or []
        text = ""
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
            text = "".join(str(p.get("text", "")) for p in parts)

        usage = data.get("usageMetadata") or {}
        tokens_in = int(usage.get("promptTokenCount") or 0)
        tokens_out = int(usage.get("candidatesTokenCount") or 0)

        self.total_tokens_input += tokens_in
        self.total_tokens_output += tokens_out
        self.request_count += 1

        content_out: Any = text
        if json_mode:
            content_out = _extract_json_object(text)

        return {
            "content": content_out,
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

