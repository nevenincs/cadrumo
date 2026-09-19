---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:5a93534d84d018635ef4f6d1ae1d23a37083d6085887945446f029e53b0d097d'
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

### deferred-schema-gates | low | Real-behaviour tests record the invariant without executing it

The source now has direct production-model coverage for accepting non-zero
result/query-token rows and rejecting all-zero rows. The gate contains no test
double or mirrored business logic, but it remains unexecuted under the current
instruction not to run tests; it is not evidence of a green runtime gate.

## Recommendations

- Ratify the pinned model and query-tokenisation contract, then generate and
  measure the committed matrix before adding the client-side cosine tier.
- Retain the non-zero-row validator as a loader/compiler invariant; prove its
  behavior later through the authorized real-behaviour gate.
- Execute the deferred schema gate only when the no-test boundary is lifted.

## Follow-up

- Ratify the pinned model and query-tokenisation contract, then generate and
  measure the committed matrix before adding the client-side cosine tier.
- Keep structured casilla resolution, lexical Pagefind cards, and legal typed
  records ahead of any future semantic expansion in the shared compose ladder.
