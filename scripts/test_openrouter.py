"""
Minimal OpenRouter connectivity test (OpenAI-compatible).

Goal:
- Verify OPENROUTER_API_KEY works
- Verify the model id exists/is available for your account
- Print a short response + usage if provided

Usage (PowerShell):
  $env:OPENROUTER_API_KEY="..."
  python scripts/test_openrouter.py --model "openai/gpt-oss-120b:free"

Usage (bash):
  OPENROUTER_API_KEY="..." python scripts/test_openrouter.py --model "openai/gpt-oss-120b:free"
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv


def main() -> int:
    # Load .env from repo root (same approach as src/config.py).
    load_dotenv(".env")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        help="OpenRouter base url (default: https://openrouter.ai/api/v1)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free"),
        help="Model id (default: openai/gpt-oss-120b:free)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENROUTER_API_KEY", ""),
        help="OpenRouter API key (default: OPENROUTER_API_KEY env/.env)",
    )
    parser.add_argument(
        "--reasoning",
        action="store_true",
        help="Enable reasoning mode via extra_body (if model/provider supports it).",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: OPENROUTER_API_KEY is empty (set env var or .env).", file=sys.stderr)
        return 2

    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        print(
            f"ERROR: python package 'openai' not installed/importable: {exc}",
            file=sys.stderr,
        )
        return 2

    client = OpenAI(base_url=args.base_url, api_key=args.api_key)

    def call(messages):
        extra_body = {"reasoning": {"enabled": True}} if args.reasoning else None
        kw = {}
        if extra_body:
            kw["extra_body"] = extra_body
        return client.chat.completions.create(model=args.model, messages=messages, **kw)

    try:
        r1 = call(
            [
                {
                    "role": "user",
                    "content": "How many r's are in the word 'strawberry'?",
                }
            ]
        )
        msg1 = r1.choices[0].message
        print("=== CALL 1 OK ===")
        print("Model:", args.model)
        print("Content:", (msg1.content or "").strip())
        if getattr(r1, "usage", None):
            u = r1.usage
            print("Usage:", getattr(u, "prompt_tokens", None), getattr(u, "completion_tokens", None))

        messages = [
            {"role": "user", "content": "How many r's are in the word 'strawberry'?"},
            {
                "role": "assistant",
                "content": msg1.content,
                # Preserve if present; some models provide it.
                **(
                    {"reasoning_details": getattr(msg1, "reasoning_details")}
                    if getattr(msg1, "reasoning_details", None) is not None
                    else {}
                ),
            },
            {"role": "user", "content": "Are you sure? Think carefully."},
        ]
        r2 = call(messages)
        msg2 = r2.choices[0].message
        print("\n=== CALL 2 OK ===")
        print("Content:", (msg2.content or "").strip())
        if getattr(r2, "usage", None):
            u = r2.usage
            print("Usage:", getattr(u, "prompt_tokens", None), getattr(u, "completion_tokens", None))

        return 0
    except Exception as exc:
        print("=== CALL FAILED ===", file=sys.stderr)
        print("Type:", exc.__class__.__name__, file=sys.stderr)
        print("Message:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

