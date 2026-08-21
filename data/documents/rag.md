# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation grounds an LLM's answer in external documents
retrieved at query time. Instead of relying solely on parametric knowledge, the
system retrieves relevant passages and passes them to the model as context.

## Why RAG improves reliability

- **Groundedness.** Answers can cite the passages that support them, which
  makes claims verifiable and reduces hallucination.
- **Freshness.** The knowledge base can be updated independently of the model.
- **Traceability.** Each answer maps back to source IDs, which is essential for
  observability and evaluation.

## Core components

1. **Chunking** documents into retrievable passages.
2. **Embedding + indexing** for semantic search.
3. **Retrieval** of the top-k most relevant passages.
4. **Generation** conditioned on the retrieved context.

## Evaluation

RAG quality is measured by retrieval relevance (did we fetch the right
passages?) and groundedness (does the answer only use retrieved evidence?).
Evidence coverage — how many claims are backed by a cited source — is a
practical heuristic signal.
