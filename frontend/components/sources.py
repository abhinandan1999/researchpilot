"""Sources rendering component."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_sources(sources: list[dict[str, Any]]) -> None:
    st.subheader("Sources")
    if not sources:
        st.info("No sources were cited.")
        return

    st.caption("Demo research sources (local / synthetic — not live web results).")
    for src in sources:
        title = src.get("title", "Untitled")
        url = src.get("url", "")
        source_id = src.get("source_id", "")
        demo = " · _demo_" if src.get("is_demo", True) else ""
        st.markdown(f"- **{title}** (`{source_id}`){demo}  \n  {url}")
