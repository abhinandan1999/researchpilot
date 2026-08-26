# 🔭 ResearchPilot

**Observable Multi-Agent Research Assistant** — a production-inspired workshop
project for the session *"Monitoring and Observability in AI Agents."*

ResearchPilot turns a complex question into a researched, verified, and cited
answer using a multi-agent workflow — while emitting the four pillars of agent
observability: **logs, metrics, traces, and evaluation**.

> This is a **production-inspired workshop architecture**, not a fully
> production-ready system. See [Known limitations](#16-troubleshooting).

## Quick Start

Needs Python 3.11+, `uv`, and an LLM provider set up first — Ollama
(default, local, free) or OpenAI. See [Prerequisites](#6-prerequisites)
for the Ollama install steps if you haven't done that yet.

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Set up environment
cp .env.example .env
# LLM_PROVIDER defaults to "ollama" — nothing else to fill in to run for
# real. To use OpenAI instead, set LLM_PROVIDER=openai and OPENAI_API_KEY.
# Langfuse keys are optional either way (for tracing).

# 3. If using Ollama: it does NOT start automatically, and this needs to
#    be running every session, not just once at install time.
curl -sS http://localhost:11434/api/version || ollama serve &

# 4. Verify your LLM provider + Langfuse actually work before relying on them
uv run python scripts/check_keys.py

# 5. Start the backend — terminal 1
uv run uvicorn backend.app.main:app --reload --port 8000

# 6. Start the frontend — terminal 2 (backend must already be running)
uv run streamlit run frontend/app.py --server.port 8501
```

Open **http://localhost:8501**, ask a question, and switch `DEMO_SCENARIO`
live from the sidebar dropdown — no `.env` edit or restart needed. See
[Environment variables](#7-environment-variables) below for details.

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
                                                        LLM Provider   Local Tools
                                                      (Ollama/OpenAI) (search/docs/source)
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

- **Python 3.11+**
- **[`uv`](https://docs.astral.sh/uv/)** — dependency management and running all commands in this README
- **An LLM provider — one of:**

  **Option A — [Ollama](https://ollama.com)** (default, `LLM_PROVIDER=ollama`).
  Runs locally, no API key, no usage cost. Needs a machine with a few GB
  free (ideally a GPU or Apple Silicon — CPU-only works but is slower).

  ```bash
  # 1. Install Ollama
  #    macOS/Linux:
  curl -fsSL https://ollama.com/install.sh | sh
  #    Windows / GUI installer: https://ollama.com/download

  # 2. Start the Ollama server (skip if it's already running as a
  #    background service after install)
  ollama serve &

  # 3. Pull the default model (~4.9 GB)
  ollama pull llama3.1:8b

  # 4. Verify it's reachable
  ollama list
  curl http://localhost:11434/api/version
  ```

  Nothing else to configure — `LLM_PROVIDER=ollama`, `OLLAMA_MODEL`, and
  `OLLAMA_BASE_URL` in `.env.example` already point at this setup.

  **Option B — OpenAI** (`LLM_PROVIDER=openai` in `.env`). Requires
  `OPENAI_API_KEY`, real usage cost, but faster and doesn't depend on
  local hardware.

  Either way: tests need neither (the LLM is mocked). The backend and
  frontend will start regardless of provider status, but
  `/api/v1/research` fails on every request until the active provider is
  actually reachable — run `uv run python scripts/check_keys.py` to
  confirm before relying on it.
- **A Langfuse Cloud account** (public + secret key) — the app runs fully
  without it, but the Traces pillar of the demo needs it. See
  [Environment variables](#7-environment-variables) and
  [Inspecting Langfuse traces](#10-inspecting-langfuse-traces).
- **VS Code** (or any editor) — this project has no editor-specific
  config checked in (no `.vscode/`), so any code editor works; VS Code is
  what this project has been developed and demoed with.
- **A modern web browser** — to use the Streamlit frontend.

## 7. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` — which LLM backend the agents call |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model (must be pulled locally) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server endpoint |
| `OPENAI_API_KEY` | – | OpenAI key (required only when `LLM_PROVIDER=openai`) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI chat model (only used when `LLM_PROVIDER=openai`) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | – | Optional tracing |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse endpoint |
| `LANGFUSE_CAPTURE_INPUT` | `false` | When `false`, raw question is NOT sent to Langfuse (only length + hash) |
| `ENVIRONMENT` | `local` | Environment tag |
| `LOG_LEVEL` | `INFO` | Log level |
| `TOOL_TIMEOUT_SECONDS` | `10` | Real per-tool timeout |
| `LLM_TIMEOUT_SECONDS` | `60` | Real per-LLM-call timeout (generous default for local Ollama inference; lower it if using OpenAI) |
| `MAX_RETRIES` | `2` | Bounded transient retries |
| `MAX_RESEARCH_ITERATIONS` | `2` | Hard loop cap |
| `MAX_QUESTION_LENGTH` | `4000` | Input validation |
| `DEMO_MODE` | `true` | Enable demo scenarios |
| `DEMO_SCENARIO` | `normal` | See [Demo scenarios](#9-demo-scenarios) |
| `BACKEND_URL` | `http://localhost:8000` | Used by the frontend |

Credentials are never hardcoded and never logged.

## 8. Example questions

- What are the most effective approaches for building reliable AI agents?
- What are reliable approaches for AI agent memory?
- How does RAG improve the groundedness of LLM applications?
- Why is tracing agentic systems different from traditional apps?

## 9. Demo scenarios

Switch scenarios live from the frontend sidebar dropdown — no restart needed.
Headless/no-UI alternative: set `DEMO_SCENARIO` (env) then restart the
backend, or export inline:

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
| `low_groundedness` | Writer cites a fabricated source outside the collected evidence; the request still **completes (200)**, but the heuristic evaluator's `groundedness` score catches it — the clearest live proof that **HTTP 200 ≠ agent success** |

Failures (and the parallel delays) are **deterministic**, never random.

## 10. Inspecting Langfuse traces

1. Add Langfuse keys to `.env` and restart the backend.
2. Run a research request from the frontend.
3. Open Langfuse → Traces. One request = one trace, named
   `<scenario>_request` (e.g. `parallel_research_request`), with nested
   spans: `planner → supervisor → {web_research ‖ kb_research} →
   aggregator → fact_check → writer`. The two `subagent:*` spans are
   **siblings that overlap in time** — the trace timeline shows them running
   in parallel. Each carries token usage per LLM call, tags (`environment`,
   `scenario:*`), the session id, and five scores: `heuristic_overall`,
   `completeness`, `groundedness`, `evidence_coverage`, and (when supplied)
   `user_feedback`.

With `LANGFUSE_CAPTURE_INPUT=false`, the raw question is replaced by
`question_length` and `question_hash`.

## 11. Logging architecture

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

## 12. Metrics endpoint

```bash
curl http://localhost:8000/api/v1/metrics
```

Returns requests (total/success/failed), latency (avg/p95), agents,
**subagents** (runs/failures/`parallel_dispatches`/`parallel_subagent_runs`),
tools (calls/failures/timeouts), retries, and LLM tokens. This is a
**workshop-local** in-process collector — not Prometheus/Grafana. Per-request
sub-agent counts (and a `subagent_reports` breakdown) are also returned in each
response's `observability` block.

## 13. Evaluation

A `heuristic_evaluation` scores **completeness**, **groundedness**, and
**evidence_coverage** in `[0,1]` (checks: summary exists, claims cite valid
source ids, writer only used collected evidence). It is a heuristic, not an
authoritative judge. Optional 👍/👎 user feedback is recorded via
`POST /api/v1/feedback`.

## 14. Concurrency model

Fully async request path. Request identity lives in **contextvars** (never
global mutable state), so concurrent users never leak context. Per-request
metrics (tokens/tool/LLM counts) are also contextvar-scoped. Simulated latency
uses `asyncio.sleep`; all I/O has real `asyncio.wait_for` timeouts.

## 15. Testing

```bash
uv run pytest
```

The LLM is mocked; Langfuse is never required. Includes tests for endpoints,
middleware, request context, **concurrent isolation**, planner validation and
fallback, graph routing, the research loop and max-iteration cap, tools,
**real timeout interruption**, retries, failure scenarios, structured logging,
metrics, evaluation, and the frontend API client.

## 16. Troubleshooting

- **`/api/v1/research` fails immediately** — check `GET /ready`'s
  `llm_configured` field. With `LLM_PROVIDER=ollama` (default), make sure
  `ollama serve` is running and the model in `OLLAMA_MODEL` is pulled
  (`ollama pull llama3.1:8b`); `uv run python scripts/check_keys.py`
  diagnoses this directly. With `LLM_PROVIDER=openai`, `OPENAI_API_KEY`
  needs to be set. Tests need neither (the LLM is mocked).
- **Ollama request hangs or times out** — a cold model load (first call
  after starting Ollama) can be slow; `LLM_TIMEOUT_SECONDS` defaults to
  `60` for this reason. Raise it further on slower/CPU-only machines.
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

1. **normal** — show Streamlit → FastAPI → LangGraph → (Ollama/OpenAI) → Langfuse.
2. **slow_search** — "the agent is slow, but where exactly?" → timeout span.
3. **search_failure** — error logs, failed span, recovery.
4. **search_retry** — attempt 1 → failure, attempt 2 → success.
5. **expensive_agent** — token usage / cost from an extra LLM call.
6. **agent_loop** — Research → Fact Check → *insufficient* → Research → Writer.
7. **parallel_research** — Supervisor fans out to two sub-agents at once; watch
   both `subagent_started` lines appear before either `subagent_completed`,
   and the overlapping sibling spans in the Langfuse trace timeline.
8. **low_groundedness** — request still returns 200/"completed", but the
   writer cites a fabricated source and the evaluator's `groundedness` score
   catches it — HTTP 200 ≠ agent success, live.

Concept map: **Logs** = what did my agent do · **Metrics** = how is it behaving ·
**Traces** = why did it behave this way · **Evaluation** = was it actually good.


## Kill a Process
#### Backend
lsof -ti:8000 | xargs kill

#### Frontend
lsof -ti:8501 | xargs kill

#### Ollama
lsof -ti:11434 | xargs kill