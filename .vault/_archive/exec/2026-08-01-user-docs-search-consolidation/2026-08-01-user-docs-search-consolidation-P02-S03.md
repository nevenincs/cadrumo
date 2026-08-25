---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:ebb1d12c33afd5327ae2be50dc83b06be7a0408b1a6a2231ffd5d0c75cf2db59'
step_id: 'S03'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---

# Author the rung-2 research record sharpening the offline-measurement caveat, the token-coverage bound, and the candidate pinned licence-clean static-embedding models with their licences and footprints

## Scope

- `.vault/research/`

## Description

- Re-ground the fired rung-2 verdict and its measurement caveat through vaultspec-rag searches over the accepted ADR, prior research, and the adjudication audit.
- Read the current miss-rate evaluator and the amended shipped-search licence rule to separate precompiled-tier evidence, token coverage, and shipping constraints.
- Compare the existing Model2Vec/potion and Qwen dense-model candidates by licence, dimension, build-time footprint, and projected matrix-size envelope.
- Author the research record with claim-first findings, re-fetchable locators, alternatives, and explicit uninvestigated decisions.

## Outcome

The research evidence sharpens the implementation boundary without selecting the model. The remediated held-out result is 32 cases / 26 hits / 0.1875 miss-rate against the 0.10 gate, but the evaluator models only precompiled tiers and is therefore an upper bound on misses in the shipped Pagefind ladder. Rung 2 remains closed-vocabulary term coverage rather than open-vocabulary semantic search: tokens absent from the matrix remain unrepresented. The existing evidence makes Model2Vec `potion-multilingual-128M` a candidate (MIT, 256 dimensions, multilingual), while Qwen3 is retained as a larger Apache-2.0 build-time comparison point; the full Potion token table is far beyond the shipped bound, so only a project-token subset can be considered. Exact model revision, vocabulary fingerprint, token inventory, encoding, quantization drift, and serialized size remain for measured compiler acceptance. The licence rule permits only a pinned, named MIT/Apache-2.0 model's provenance-stamped plain-data matrix in built docs, capped at 3 MB and excluded from the wheel. The architecture consultation recommends building this compiler model-agnostically before pinning or committing a matrix.

## Notes

The research record is source-only and does not make the ADR decision. No model download, benchmark, matrix generation, browser probe, test, deployment, or live-service probe was run. The P02.S03 plan row is closed because the research artifact and execution record are present and VaultSpec health is clean; downstream compiler work must not infer a model choice from this record. A focused architecture consultation recommends a model-agnostic compiler with explicit vocabulary/model/artifact hashes, deterministic quantization, per-term coverage, and a hard 3,000,000-byte serialized ceiling; model pinning and matrix acceptance remain measured follow-up work.
