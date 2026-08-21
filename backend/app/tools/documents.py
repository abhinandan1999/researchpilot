"""The ``search_documents`` tool.

Searches local markdown documents under ``data/documents/`` and returns
the most relevant passages. Documents are loaded and cached in memory.
"""

from __future__ import annotations

import re
from functools import lru_cache

from backend.app.config import settings
from backend.app.models.schemas import DocumentPassage, DocumentSearchResult
from backend.app.tools.base import guarded_tool_call
from backend.app.utils.errors import ToolError


@lru_cache(maxsize=1)
def _load_documents() -> tuple[tuple[str, str, list[str]], ...]:
    """Load documents as (name, title, paragraphs). Cached."""

    docs_dir = settings.documents_dir
    if not docs_dir.exists():
        raise ToolError(f"Documents directory not found: {docs_dir}")

    loaded: list[tuple[str, str, list[str]]] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Title = first markdown H1, fallback to filename.
        title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        loaded.append((path.name, title, paragraphs))
    return tuple(loaded)


def _score(query: str, paragraph: str) -> float:
    terms = {t for t in re.findall(r"\w+", query.lower()) if len(t) > 2}
    if not terms:
        return 0.0
    hay = paragraph.lower()
    hits = sum(1 for t in terms if t in hay)
    return min(1.0, round(hits / len(terms), 3))


async def search_documents(query: str, limit: int = 4) -> DocumentSearchResult:
    """Return the most relevant passages from local documents."""

    if not isinstance(query, str) or not query.strip():
        raise ToolError("document query must be a non-empty string")

    async def _run() -> DocumentSearchResult:
        candidates: list[tuple[float, DocumentPassage]] = []
        for name, title, paragraphs in _load_documents():
            for para in paragraphs:
                if para.startswith("#"):
                    continue
                relevance = _score(query, para)
                if relevance > 0:
                    candidates.append(
                        (
                            relevance,
                            DocumentPassage(
                                document=name,
                                title=title,
                                passage=para,
                                relevance=relevance,
                            ),
                        )
                    )
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        passages = [p for _, p in candidates[:limit]]
        return DocumentSearchResult(query=query, passages=passages)

    return await guarded_tool_call(
        "search_documents", _run, query_length=len(query)
    )
