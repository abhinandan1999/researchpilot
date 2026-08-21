"""Report rendering component."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.utils.formatting import format_confidence


def render_report(report: dict[str, Any]) -> None:
    if not report:
        st.warning("No report was returned.")
        return

    st.subheader("Summary")
    st.write(report.get("summary", "-"))

    confidence = report.get("confidence")
    st.metric("Confidence", format_confidence(confidence))

    key_findings = report.get("key_findings") or []
    if key_findings:
        st.subheader("Key Findings")
        for finding in key_findings:
            st.markdown(f"- {finding}")

    analysis = report.get("analysis")
    if analysis:
        st.subheader("Detailed Analysis")
        st.write(analysis)
