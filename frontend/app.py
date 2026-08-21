"""ResearchPilot Streamlit frontend.

A thin HTTP client for the FastAPI backend. This file contains NO agent,
LangGraph, or tool code — all orchestration happens in the backend.
"""

from __future__ import annotations

import uuid

import streamlit as st

from frontend.api_client import ApiClient
from frontend.components.header import render_header
from frontend.components.progress import STAGES
from frontend.components.report import render_report
from frontend.components.sources import render_sources
from frontend.utils.formatting import format_duration, format_score, safe_get

st.set_page_config(page_title="ResearchPilot", page_icon="🔭", layout="wide")

EXAMPLE_QUESTIONS = [
    "What are the most effective approaches for building reliable AI agents?",
    "What are reliable approaches for AI agent memory?",
    "How does RAG improve the groundedness of LLM applications?",
    "Why is tracing agentic systems different from traditional apps?",
]

# Mirrors the table in README.md ("Demo scenarios") for in-app reference.
SCENARIO_DESCRIPTIONS = {
    "normal": "Happy path end-to-end.",
    "slow_search": "Search waits ~5s; TOOL_TIMEOUT_SECONDS interrupts it (timeout span/metric).",
    "search_failure": "Tool call fails outright; failed span, agent recovers.",
    "search_retry": "Attempt 1 fails, attempt 2 succeeds (retry_started).",
    "expensive_agent": "Extra redundant LLM call; higher token/cost visibility.",
    "agent_loop": "Fact checker forces one extra research iteration (max 2).",
    "parallel_research": "Web/KB sub-agents get staggered delays so their parallel dispatch/completion interleaves in logs and traces.",
}


def _init_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"sess_{uuid.uuid4().hex}"
    if "result" not in st.session_state:
        st.session_state.result = None
    if "feedback_sent" not in st.session_state:
        st.session_state.feedback_sent = False


def _render_sidebar(client: ApiClient) -> None:
    with st.sidebar:
        st.header("Session")
        st.code(st.session_state.session_id, language="text")

        st.header("Backend")
        try:
            ready = client.ready()
            st.success("Connected")
            st.write(
                f"OpenAI configured: **{ready.get('openai_configured', False)}**"
            )
            st.write(
                f"Langfuse configured: **{ready.get('langfuse_configured', False)}**"
            )
        except Exception:
            st.error("Backend unreachable")
            st.caption("Start it with:\n`uv run uvicorn backend.app.main:app --port 8000`")
            return

        st.header("Demo scenario")
        try:
            info = client.get_demo_scenario()
            options = info.get("options") or [info.get("demo_scenario", "normal")]
            current = info.get("demo_scenario", "normal")
            selected = st.selectbox(
                "Scenario",
                options=options,
                index=options.index(current) if current in options else 0,
                label_visibility="collapsed",
            )
            st.caption(SCENARIO_DESCRIPTIONS.get(selected, ""))
            if not info.get("demo_mode", True):
                st.warning("DEMO_MODE is off — set it in .env for scenarios to take effect.")
            if selected != current:
                client.set_demo_scenario(selected)
                st.rerun()
        except Exception:
            st.caption("Demo scenario control unavailable.")

        with st.expander("Live metrics"):
            try:
                st.json(client.metrics())
            except Exception:
                st.caption("Metrics unavailable.")


def _render_observability(result) -> None:
    obs = safe_get(result.data, "observability", default={}) or {}
    evaluation = safe_get(result.data, "evaluation", default={}) or {}
    with st.expander("🔎 Observability", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.text_input("Request ID", result.request_id or "-", disabled=True)
        c2.text_input("Trace ID", result.trace_id or "-", disabled=True)
        c3.text_input("Session ID", result.session_id or "-", disabled=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Duration", format_duration(obs.get("duration_ms")))
        m2.metric("Agents", obs.get("agent_count", 0))
        m3.metric("Tool calls", obs.get("tool_call_count", 0))
        m4.metric("LLM calls", obs.get("llm_call_count", 0))

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Input tokens", obs.get("input_tokens", 0))
        t2.metric("Output tokens", obs.get("output_tokens", 0))
        t3.metric("Iterations", obs.get("iterations", 0))
        t4.metric("Retries", obs.get("retries", 0))

        s1, s2 = st.columns(2)
        s1.metric("Sub-agents run", obs.get("subagent_count", 0))
        s2.metric("Parallel dispatches", obs.get("parallel_dispatches", 0))

        subagent_reports = obs.get("subagent_reports", []) or []
        if subagent_reports:
            st.caption("Parallel sub-agents (concurrent research fan-out):")
            for rep in subagent_reports:
                st.markdown(
                    f"- **{rep.get('agent', '?')}** "
                    f"({rep.get('parallel_group', 'research')}): "
                    f"{rep.get('source_count', 0)} sources, "
                    f"{rep.get('finding_count', 0)} findings, "
                    f"{rep.get('error_count', 0)} errors, "
                    f"{format_duration(rep.get('duration_ms'))}"
                )

        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Eval overall", format_score(evaluation.get("overall")))
        e2.metric("Completeness", format_score(evaluation.get("completeness")))
        e3.metric("Groundedness", format_score(evaluation.get("groundedness")))
        e4.metric("Evidence cov.", format_score(evaluation.get("evidence_coverage")))

        if evaluation.get("notes"):
            st.caption("Heuristic evaluation notes:")
            for note in evaluation["notes"]:
                st.markdown(f"- {note}")

        errors = safe_get(result.data, "errors", default=[]) or []
        if errors:
            st.warning("Tool/agent errors occurred during research:")
            st.json(errors)


def _render_feedback(client: ApiClient, request_id: str) -> None:
    st.subheader("Was this useful?")
    col_up, col_down, _ = st.columns([1, 1, 6])
    if col_up.button("👍", use_container_width=True):
        st.session_state.feedback_sent = client.send_feedback(request_id, True)
    if col_down.button("👎", use_container_width=True):
        st.session_state.feedback_sent = client.send_feedback(request_id, False)
    if st.session_state.feedback_sent:
        st.success("Thanks for your feedback!")


def main() -> None:
    _init_state()
    client = ApiClient()

    render_header()
    _render_sidebar(client)

    st.subheader("Research Question")
    question = st.text_area(
        "Enter a complex question",
        value=EXAMPLE_QUESTIONS[0],
        height=100,
        label_visibility="collapsed",
    )
    with st.expander("Example questions"):
        for q in EXAMPLE_QUESTIONS:
            st.markdown(f"- {q}")

    if st.button("🚀 Start Research", type="primary"):
        st.session_state.feedback_sent = False
        progress_box = st.empty()
        with progress_box.container():
            st.markdown("\n\n".join(f"● {s}" for s in STAGES))
        with st.spinner("Running multi-agent research..."):
            result = client.research(
                question, session_id=st.session_state.session_id
            )
        progress_box.empty()
        st.session_state.result = result

    result = st.session_state.result
    if result is not None:
        if result.ok:
            progress_done = "  ".join(f"✓ {s}" for s in STAGES)
            st.markdown(progress_done)
            report = safe_get(result.data, "report", default={}) or {}
            render_report(report)
            render_sources(report.get("sources") or [])
            _render_observability(result)
            if result.request_id:
                _render_feedback(client, result.request_id)
        else:
            st.error(f"Research failed ({result.status_code}): {result.error}")


if __name__ == "__main__":
    main()
