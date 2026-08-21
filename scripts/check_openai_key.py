"""Verify OPENAI_API_KEY is valid with one minimal, cheap API call.

This is a manual connectivity check, not a pytest test: the automated
suite intentionally mocks the LLM and must never require real network
access or a real key (see tests/backend/conftest.py). Run this by hand
before a workshop/demo to confirm the configured key actually works.

Usage:
    uv run python scripts/check_openai_key.py

The response is capped at 100 output tokens to keep the cost negligible.
The API key itself is never printed.
"""

from __future__ import annotations

import sys

from backend.app.config import settings


def main() -> int:
    if not settings.openai_configured:
        print("FAIL: OPENAI_API_KEY is not set in .env")
        return 1

    from openai import (
        APIConnectionError,
        AuthenticationError,
        OpenAI,
        OpenAIError,
        RateLimitError,
    )

    client = OpenAI(api_key=settings.openai_api_key)

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            max_tokens=100,
        )
    except AuthenticationError:
        print(f"FAIL: key was rejected by OpenAI (invalid or revoked key)")
        return 1
    except RateLimitError as exc:
        print(f"FAIL: rate-limited or out of quota ({exc})")
        return 1
    except APIConnectionError as exc:
        print(f"FAIL: could not reach OpenAI ({exc})")
        return 1
    except OpenAIError as exc:
        print(f"FAIL: OpenAI API error ({exc})")
        return 1

    choice = response.choices[0].message.content if response.choices else None
    usage = response.usage

    print("OK: key is valid, model responded")
    print(f"  model: {response.model}")
    print(f"  reply: {choice!r}")
    if usage:
        print(
            f"  tokens: input={usage.prompt_tokens} "
            f"output={usage.completion_tokens} total={usage.total_tokens}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
