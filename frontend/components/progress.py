"""Progress indicator component."""

from __future__ import annotations

import streamlit as st

STAGES = [
    "Planning research",
    "Researching sources",
    "Checking evidence",
    "Writing report",
]


def render_progress(active_index: int) -> None:
    """Render a simple staged progress list.

    ``active_index`` marks the currently-running stage; earlier stages are
    shown as complete.
    """

    lines = []
    for i, stage in enumerate(STAGES):
        if i < active_index:
            lines.append(f"✓ {stage}")
        elif i == active_index:
            lines.append(f"● {stage}")
        else:
            lines.append(f"○ {stage}")
    st.markdown("\n\n".join(lines))
