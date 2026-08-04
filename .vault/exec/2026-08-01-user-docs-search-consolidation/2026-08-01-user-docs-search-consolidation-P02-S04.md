---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:9af4e8cf887ec45d8b9d24a2dfd07e3f7b5606390a0e7910c33b4d772da1e583'
step_id: 'S04'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---

# Build the dev-side matrix compiler that embeds the closed vocabulary and its token inventory with the pinned model and emits the bounded int8 matrix as committed, reviewable, provenance-stamped data

## Scope

- `dev/docs/`

## Description

- Re-ground the compiler boundary with vaultspec-rag over the accepted ADR, P02.S03 research, the active plan, and the existing terminology sweep/miss-rate code.
- Add a model-agnostic dev-side compiler contract that canonicalises the closed vocabulary and records its SHA-256 fingerprint and deterministic row order.
- Require one finite, token-count-consistent provider observation per term, reject missing/duplicate/foreign rows, normalise vectors with float32 arithmetic, and emit symmetric per-row int8 values with explicit scales.
- Stamp the plain-data matrix with model repository, immutable revision, SPDX licence, dimension, token inventory, quantisation algorithm, serialized byte count, and artifact hash.
- Export the compiler surface through the terminology dev package and run source-only AST and whitespace checks.

## Outcome

The deterministic source seam for P02.S04 now exists in the dev tooling. It is deliberately model-agnostic: the provider must supply a pinned model metadata record and exact tokenised embeddings, while the compiler owns canonical vocabulary identity, coverage failures, quantisation, self-attestation, and the 3,000,000-byte hard ceiling. The browser and shipped product remain untouched.

P02.S04 is not closed. No model was selected or downloaded, no provider adapter or committed matrix was generated, and no client cosine tier or licence gate was added. Those remain measured follow-up work under P02.S04-P02.S07.

## Notes

The change was grounded by vaultspec-rag searches over the existing sweep, miss-rate evaluator, terminology package, accepted consolidation ADR, and Rung-2 research. The configured codebase alias rejection was not bypassed and no reindex was requested.

No tests, builds, model downloads, matrix generation, browser probes, live-service sweeps, deployment, or runtime gates were run. The formal source review is recorded separately and must pass before any future plan-state transition.

The formal remediation review recorded PASS for the four compiler strictness findings: required schema markers, exact canonical provider identity, float32 scale representation, and raw canonical artifact bytes. Vocabulary-source provenance and aggregate token-coverage evidence remain LOW follow-ons for P02.S05-P02.S07. The P02.S04 plan row remains open because this source seam has no ratified provider, generated matrix, or measured acceptance artifact yet.
