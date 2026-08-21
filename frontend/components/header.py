"""Header component."""

from __future__ import annotations

import streamlit as st


def render_header() -> None:
    st.title("🔭 ResearchPilot")
    st.caption("Observable Multi-Agent Research Assistant")
    st.markdown(
        "Ask a complex question. **ResearchPilot** plans the investigation, "
        "gathers evidence, verifies claims, and produces a cited answer — "
        "while emitting logs, metrics, and traces you can inspect."
    )
