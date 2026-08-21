"""Verify LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are valid.

This is a manual connectivity check, not a pytest test: the automated
suite never requires Langfuse (see README - "Langfuse is never
required"). Run this by hand before a workshop/demo to confirm tracing
will actually light up.

Usage:
    uv run python scripts/check_langfuse_keys.py

Uses the SDK's built-in auth_check(), which calls the Langfuse projects
API once. No traces/spans are created and no LLM is called, so this has
no OpenAI cost.
"""

from __future__ import annotations

import sys

from backend.app.config import settings


def main() -> int:
    if not settings.langfuse_configured:
        print("FAIL: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set in .env")
        return 1

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
        return 1

    print("OK: Langfuse keys are valid")
    print(f"  host: {settings.langfuse_host}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
