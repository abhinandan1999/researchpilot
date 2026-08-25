"""Verify OPENAI_API_KEY and Langfuse credentials are valid.

This is a manual connectivity check, not a pytest test: the automated
suite intentionally mocks the LLM and never requires Langfuse (see
tests/backend/conftest.py and the README). Run this by hand before a
workshop/demo to confirm both integrations will actually work.

Usage:
    uv run python scripts/check_keys.py

Checks OpenAI first, then Langfuse, and always runs both even if the
first fails, so you get a full picture in one pass. The OpenAI check
makes one minimal chat completion capped at 100 output tokens (trivial
cost). The Langfuse check uses the SDK's built-in auth_check() — one
call to the projects API, no traces/spans created, no OpenAI cost.
Neither check ever prints a secret key.
"""

from __future__ import annotations

import sys

from backend.app.config import settings


def check_openai() -> bool:
    print("--- OpenAI ---")
    if not settings.openai_configured:
        print("FAIL: OPENAI_API_KEY is not set in .env")
        return False

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
        print("FAIL: key was rejected by OpenAI (invalid or revoked key)")
        return False
    except RateLimitError as exc:
        print(f"FAIL: rate-limited or out of quota ({exc})")
        return False
    except APIConnectionError as exc:
        print(f"FAIL: could not reach OpenAI ({exc})")
        return False
    except OpenAIError as exc:
        print(f"FAIL: OpenAI API error ({exc})")
        return False

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
    return True


def check_langfuse() -> bool:
    print("--- Langfuse ---")
    if not settings.langfuse_configured:
        print("FAIL: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set in .env")
        return False

    from langfuse import Langfuse

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    try:
        client.auth_check()
    except Exception as exc:  # noqa: BLE001 - surface whatever the SDK raises
        print(f"FAIL: Langfuse auth check failed ({exc})")
        print(f"  host: {settings.langfuse_host}")
        return False

    print("OK: Langfuse keys are valid")
    print(f"  host: {settings.langfuse_host}")
    return True


def main() -> int:
    openai_ok = check_openai()
    print()
    langfuse_ok = check_langfuse()
    print()

    print("--- Summary ---")
    print(f"  OpenAI:   {'OK' if openai_ok else 'FAIL'}")
    print(f"  Langfuse: {'OK' if langfuse_ok else 'FAIL'}")

    return 0 if (openai_ok and langfuse_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
