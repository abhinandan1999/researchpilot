"""Source loading and the ``get_source`` tool.

Sources are loaded from ``data/mock_search/sources.json`` and cached in
memory (the dataset is tiny). All returned data is clearly marked as demo
data via ``is_demo=True``.
"""

from __future__ import annotations

import json
from functools import lru_cache

from backend.app.config import settings
from backend.app.models.schemas import Source
from backend.app.tools.base import guarded_tool_call
from backend.app.utils.errors import ToolError, ValidationError


@lru_cache(maxsize=1)
def _load_raw_sources() -> tuple[Source, ...]:
    """Load and validate all demo sources from disk (cached)."""

    path = settings.mock_search_file
    if not path.exists():
        raise ToolError(f"Mock source file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ToolError(f"Invalid sources.json: {exc}") from exc

    sources: list[Source] = []
    for item in raw:
        sources.append(
            Source(
                source_id=item["source_id"],
                title=item["title"],
                url=item["url"],
                topic=item.get("topic", ""),
                snippet=item.get("content", ""),
                published_at=item.get("published_at"),
                is_demo=True,
            )
        )
    return tuple(sources)


def load_all_sources() -> list[Source]:
    """Return all demo sources."""

    return list(_load_raw_sources())


async def get_source(source_id: str) -> Source:
    """Retrieve a single demo source by its ``source_id``.

    Raises :class:`ValidationError` if the id is unknown.
    """

    if not source_id or not isinstance(source_id, str):
        raise ValidationError("source_id must be a non-empty string")

    async def _run() -> Source:
        for source in load_all_sources():
            if source.source_id == source_id:
                return source
        raise ValidationError(f"Unknown source_id: {source_id}")

    return await guarded_tool_call("get_source", _run, source_id=source_id)
