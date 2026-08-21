# 🔭 ResearchPilot

**Observable Multi-Agent Research Assistant** — a production-inspired workshop
project for the session *"Monitoring and Observability in AI Agents."*

ResearchPilot turns a complex question into a researched, verified, and cited
answer using a multi-agent workflow — while emitting the four pillars of agent
observability: **logs, metrics, traces, and evaluation**.

> This is a **production-inspired workshop architecture**, not a fully
> production-ready system. See [Known limitations](#19-troubleshooting).

---

## 1. What is ResearchPilot?

A user asks a research question in a **Streamlit** frontend. The frontend calls
a **FastAPI** backend over HTTP only. The backend runs a **LangGraph**
**supervisor / sub-agent** workflow:

- **Planner** (LLM) — breaks the question into allow-listed research tasks
- **Supervisor** — splits the plan by capability and dispatches two research
  sub-agents that run **in parallel** (fan-out)
  - **Web Research sub-agent** — external demo/web-style sources
    (`search_sources`, `get_source`)
  - **Knowledge-Base sub-agent** — the local markdown knowledge base
    (`search_documents`)
- **Aggregator** — the fan-in join that waits for both sub-agents
- **Fact Checker** (LLM) — verifies evidence, decides if more research is needed
  (can loop back to the supervisor)
- **Writer** (LLM) — writes a grounded, cited report

Every step — including each parallel sub-agent — is logged (structlog JSON),
counted (in-process metrics), and traced (Langfuse). A heuristic evaluator
scores the result.

## 2. Architecture

```
┌──────────────────────────┐        HTTP/JSON        ┌──────────────────────────┐
│    Streamlit Frontend    │ ───────────────────────▶│     FastAPI Backend      │
│  (client only, no agents)│                         │ middleware: req/trace/   │
└──────────────────────────┘                         │ session ids + logging    │
                                                      │            │             │
                                                      │            ▼             │
                                                      │        LangGraph         │
                                                      │  Planner → Supervisor    │
                                                      │   ├─▶ Web Research  ┐     │
                                                      │   └─▶ KB Research   ┘ ║   │
                                                      │        (parallel)   ▼    │
                                                      │      Aggregator → Fact   │
                                                      │      Check → (loop?) →    │
                                                      │            Writer        │
                                                      └──────┬─────────────┬─────┘
                                                             ▼             ▼
                                                          OpenAI      Local Tools
                                                                     (search/docs/source)
                                                             │
                                                             ▼
                                                          Langfuse
                                              logs · traces · tokens · cost · eval
```

Graph flow (see [`docs/graph.png`](docs/graph.png)):

```
                         ┌────────────── parallel ──────────────┐
START → planner → supervisor ─┬─▶ web_research ─┐                │
            ▲                 └─▶ kb_research  ─┴─▶ aggregator → fact_check
            │ no (iteration < 2)                                    │
            └────────────────────────────────────────────────── loop?
                                                     sufficient? ──▶ writer → END
```

The **supervisor** fans out to two sub-agents that execute concurrently; the
**aggregator** is the fan-in join (it runs only once *both* sub-agents finish).
Because the sub-agents only write to additive-reducer state fields, their
concurrent updates merge safely. Maximum research iterations: **2** (loops can
never run forever).

## 3. Why LangGraph?

LangGraph is the single orchestration framework. It models the *dynamic,
branching, looping* nature of agentic workflows — a **supervisor** that
**fans out** to parallel sub-agents (and a fact-checker that can send work
back for another pass) — with a typed state, additive reducers that merge
concurrent updates safely, and explicit conditional edges. That is exactly
what makes agent traces interesting to observe: parallel spans, fan-in joins,
and bounded loops.

## 4. Why Langfuse?

Langfuse gives one logical **trace per request** with nested spans for each
agent, tool, and LLM call, plus token/cost and evaluation scores. It answers
*"why did my agent behave this way?"* The app runs fully **without** Langfuse;
add credentials to light up tracing.

## 5. Frontend / backend separation

The Streamlit app imports **no** backend, LangGraph, or tool code. It talks to
FastAPI purely over HTTP via [`frontend/api_client.py`](frontend/api_client.py).
All agent execution happens in the backend.

## 6. Prerequisites

- Python **3.11+**
- [`uv`](https://docs.astral.sh/uv/)
- An OpenAI API key (for real research runs)
- *(Optional)* Langfuse Cloud keys (for tracing)

## 7. uv setup

```bash
uv sync --extra dev
```

Copy the environment template and fill in your keys:

```bash
cp .env.example .env
```

## 8. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | – | OpenAI key (required for research) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | – | Optional tracing |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse endpoint |
| `LANGFUSE_CAPTURE_INPUT` | `false` | When `false`, raw question is NOT sent to Langfuse (only length + hash) |
| `ENVIRONMENT` | `local` | Environment tag |
| `LOG_LEVEL` | `INFO` | Log level |
| `TOOL_TIMEOUT_SECONDS` | `10` | Real per-tool timeout |
| `LLM_TIMEOUT_SECONDS` | `30` | Real per-LLM-call timeout |
| `MAX_RETRIES` | `2` | Bounded transient retries |
| `MAX_RESEARCH_ITERATIONS` | `2` | Hard loop cap |
| `MAX_QUESTION_LENGTH` | `4000` | Input validation |
| `DEMO_MODE` | `true` | Enable demo scenarios |
| `DEMO_SCENARIO` | `normal` | See [Demo scenarios](#12-demo-scenarios) |
| `BACKEND_URL` | `http://localhost:8000` | Used by the frontend |

Credentials are never hardcoded and never logged.

## 9. Start the backend

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

## 10. Start the frontend

```bash
uv run streamlit run frontend/app.py --server.port 8501
```

Open http://localhost:8501.

## 11. Example questions

- What are the most effective approaches for building reliable AI agents?
- What are reliable approaches for AI agent memory?
- How does RAG improve the groundedness of LLM applications?
- Why is tracing agentic systems different from traditional apps?

## 12. Demo scenarios

Set `DEMO_SCENARIO` (env) then restart the backend, or export inline:

```bash
# Windows PowerShell
$env:DEMO_SCENARIO="slow_search"; uv run uvicorn backend.app.main:app --port 8000
```

| Scenario | Demonstrates |
|---|---|
| `normal` | Happy path end-to-end |
| `slow_search` | Real timeout (search waits ~5s, `TOOL_TIMEOUT_SECONDS=3`), error span, timeout metric, graceful handling |
| `search_failure` | Tool failure, failed span, agent recovery |
| `search_retry` | Attempt 1 fails → attempt 2 succeeds (`retry_started`) |
| `expensive_agent` | Extra LLM call → higher token/cost visibility |
| `agent_loop` | Fact checker forces one extra research iteration (max 2) |
| `parallel_research` | Supervisor dispatches **two sub-agents in parallel**; each is given a distinct, deterministic delay (web ≈1.5s, kb ≈0.5s) so their `subagent_started`/`subagent_completed` log lines **interleave** — making concurrent execution visible in logs, metrics, and traces |

Failures (and the parallel delays) are **deterministic**, never random.

## 13. Inspecting Langfuse traces

1. Add Langfuse keys to `.env` and restart the backend.
2. Run a research request from the frontend.
3. Open Langfuse → Traces. One request = one trace, with nested spans:
   `research_request → planner → supervisor → {web_research ‖ kb_research}
   → aggregator → fact_check → writer`. The two `subagent:*` spans are
   **siblings that overlap in time** — the trace timeline shows them running
   in parallel. Each carries token usage per LLM call, tags (`environment`,
   `scenario:*`), the session id, and the `heuristic_overall` /
   `user_feedback` scores.

With `LANGFUSE_CAPTURE_INPUT=false`, the raw question is replaced by
`question_length` and `question_hash`.

## 14. Logging architecture

Structured JSON via **structlog**. Every line includes `timestamp`, `level`,
`service`, `event`, and — when in a request — `request_id`, `trace_id`,
`session_id`. Key events: `request_started/completed`,
`agent_started/completed/failed`, `supervisor_dispatch`,
`subagent_started/completed/failed` (each tagged with `agent` and
`parallel_group`), `subagents_joined`,
`tool_started/completed/failed/timeout`, `retry_started`,
`research_iteration_started/completed`, `evaluation_completed`. Because the
sub-agents run concurrently, their log lines interleave — the shared
`request_id`/`trace_id` plus the per-line `agent` field are what let you
re-thread a single sub-agent's story out of the interleaved stream. Secrets
are redacted; prompts/responses are not dumped by default.

## 15. Metrics endpoint

```bash
curl http://localhost:8000/api/v1/metrics
```

Returns requests (total/success/failed), latency (avg/p95), agents,
**subagents** (runs/failures/`parallel_dispatches`/`parallel_subagent_runs`),
tools (calls/failures/timeouts), retries, and LLM tokens. This is a
**workshop-local** in-process collector — not Prometheus/Grafana. Per-request
sub-agent counts (and a `subagent_reports` breakdown) are also returned in each
response's `observability` block.

## 16. Evaluation

A `heuristic_evaluation` scores **completeness**, **groundedness**, and
**evidence_coverage** in `[0,1]` (checks: summary exists, claims cite valid
source ids, writer only used collected evidence). It is a heuristic, not an
authoritative judge. Optional 👍/👎 user feedback is recorded via
`POST /api/v1/feedback`.

## 17. Concurrency model

Fully async request path. Request identity lives in **contextvars** (never
global mutable state), so concurrent users never leak context. Per-request
metrics (tokens/tool/LLM counts) are also contextvar-scoped. Simulated latency
uses `asyncio.sleep`; all I/O has real `asyncio.wait_for` timeouts.

## 18. Testing

```bash
uv run pytest
```

OpenAI is mocked; Langfuse is never required. Includes tests for endpoints,
middleware, request context, **concurrent isolation**, planner validation and
fallback, graph routing, the research loop and max-iteration cap, tools,
**real timeout interruption**, retries, failure scenarios, structured logging,
metrics, evaluation, and the frontend API client.

## 19. Troubleshooting

- **`OPENAI_API_KEY is not configured`** — real research needs a key in `.env`.
  Tests do not (LLM is mocked).
- **Frontend says "Backend unreachable"** — start the backend on port 8000.
- **No Langfuse traces** — set both Langfuse keys and restart.
- **Import errors running Streamlit** — run `uv sync` so the `frontend` and
  `backend` packages are installed; run commands from the project root.

### Known limitations

- Local, in-memory metrics and result store (not distributed/persistent).
- Mock/demo sources only — no live web search.
- Heuristic evaluation is indicative, not authoritative.
- Single-process; no auth. **Production-inspired workshop architecture.**

## Workshop demo sequence

1. **normal** — show Streamlit → FastAPI → LangGraph → (OpenAI) → Langfuse.
2. **slow_search** — "the agent is slow, but where exactly?" → timeout span.
3. **search_failure** — error logs, failed span, recovery.
4. **search_retry** — attempt 1 → failure, attempt 2 → success.
5. **expensive_agent** — token usage / cost from an extra LLM call.
6. **agent_loop** — Research → Fact Check → *insufficient* → Research → Writer.
7. **parallel_research** — Supervisor fans out to two sub-agents at once; watch
   both `subagent_started` lines appear before either `subagent_completed`,
   and the overlapping sibling spans in the Langfuse trace timeline.

Concept map: **Logs** = what did my agent do · **Metrics** = how is it behaving ·
**Traces** = why did it behave this way · **Evaluation** = was it actually good.
