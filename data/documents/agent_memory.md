# Agent Memory

Memory lets an agent carry information across steps and sessions. Choosing the
right memory strategy is central to building reliable agents.

## Types of memory

- **Short-term (working) memory.** The current context window: the running
  conversation, intermediate results, and scratchpad reasoning. It is fast but
  bounded by the model's context length.
- **Long-term memory.** Durable storage of facts, past interactions, or
  distilled summaries, retrieved on demand. Often implemented with a vector
  store (retrieval-based memory).
- **Retrieval-based memory.** A hybrid where relevant long-term items are
  fetched into short-term context via semantic search, similar to RAG.

## Trade-offs

- Larger context windows reduce the need for retrieval but increase cost and
  latency and can dilute attention.
- Long-term memory improves continuity but introduces retrieval errors and
  staleness.
- Summarization compresses history but can lose detail.

## Evaluation approaches

Memory quality is evaluated by recall (did the agent remember the right
thing?), precision (did it avoid injecting irrelevant memories?), and
consistency across turns.
