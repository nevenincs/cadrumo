---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d44e43453dcb61b0bf470e03b2df45eb7a9a31753f30a83a7bb18f460e4a7b17'
related: []
---

# `user-docs-search-consolidation` audit: `P02.S04 query-token matrix contract review`

## Scope

Review the source-only P02.S04 query-token matrix continuation against the
RAG-grounded consolidation ADR, Rung-2 boundary research, the preceding
compiler audit, and the Sol-medium architecture recommendation. The review is
limited to the compiler contract and package exports; no artifact or runtime
surface is in scope.

## Findings

### query-token-contract | low | Source seam is explicit but not an acceptance artifact

The source-only continuation separates candidate result rows from
browser-recognizable query-token rows, carries exact token identity and model
token id, fingerprints both vocabularies, and preserves the existing strict
dimension, quantisation, canonical-byte, provenance, and 3,000,000-byte
invariants. This is the contract recommended by the Sol-medium architecture
review and the RAG-grounded Rung-2 boundary. No model/provider adapter,
generated matrix, browser reader, or runtime result is present, so this does
not prove P02.S04 or P02.S05 acceptance.

### model-and-measurement-gate | low | Model and cosine acceptance remain open

The accepted research still requires model revision/licence ratification,
tokenizer and normalisation evidence, quantisation-drift measurements, and
held-out recall evidence before a matrix can ship. The plan rows remain open;
no model download, artifact generation, test, build, browser probe, sweep, or
deployment was performed for this continuation.

### nonzero-row-invariant | low | Quantized rows now fail closed when all values are zero

The schema-v2 source contract now rejects all-zero int8 values for both
candidate-result rows and browser-recognizable query-token rows. This preserves
the RAG-grounded requirement that every admitted row represent a finite,
non-zero vector, including when a future artifact is loaded rather than
compiled locally. It does not select a model or establish quantization-drift
acceptance.

## Recommendations

- Ratify the pinned model and query-tokenisation contract, then generate and
  measure the committed matrix before adding the client-side cosine tier.
- Retain the non-zero-row validator as a loader/compiler invariant; prove its
  behavior later through the authorized real-behaviour gate.

## Follow-up

- Ratify the pinned model and query-tokenisation contract, then generate and
  measure the committed matrix before adding the client-side cosine tier.
- Keep structured casilla resolution, lexical Pagefind cards, and legal typed
  records ahead of any future semantic expansion in the shared compose ladder.
