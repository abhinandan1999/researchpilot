# Observability for AI Agents

Observability is the practice of understanding a system's internal state from
its external outputs. For AI agents it answers four questions:

- **Logs — "What did my agent do?"** Structured, event-based records of each
  step: agent started, tool called, retry triggered, iteration completed.
- **Metrics — "How is my agent behaving?"** Aggregate numbers such as request
  counts, latency percentiles, tool failure rates, token usage, and cost.
- **Traces — "Why did my agent behave this way?"** A causal tree linking the
  HTTP request to each agent, tool, and LLM call, with timing and token data.
- **Evaluation — "Was the agent actually good?"** Heuristic or model-based
  scoring of completeness, groundedness, and evidence coverage.

## Why tracing agents is different

Traditional request/response tracing is largely linear. Agentic systems branch
and loop: a fact-checker may send the workflow back to research, tools may time
out and retry, and a single request can trigger many LLM calls. Traces must
capture this dynamic, non-linear structure.

## Correlation identifiers

A `request_id`, `trace_id`, and `session_id` should flow from the frontend
through the API, the orchestration graph, each agent, and every external call.
This correlation is what makes end-to-end debugging possible.

## Privacy

Telemetry must redact secrets and pseudonymize user identity. Raw prompts and
user questions should only be captured when explicitly enabled for debugging.
