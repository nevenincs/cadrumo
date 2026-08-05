---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:48608208a67700024952afdd8e527f69e35aa702dec08da2da96624e3a45bcf3'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
  - "[[2026-08-05-user-docs-search-consolidation-source-contract-reference]]"
---

# `user-docs-search-consolidation` audit: `Rung-2 evaluator source review`

## Scope

Audit the new source-only Rung-2 held-out measurement primitive against the accepted ADR, the source contract reference, the browser semantic implementation, the validated bundle/quantized matrix models, and the existing pre-Rung-2 evaluator. The review is intentionally source-only: tests, builds, artifacts, runtime probes, and deployment are out of scope under the current operator boundary.

## Findings

### rung2-evaluator | medium | The primitive is semantic-tier measurement, not the full P02.S07 ladder report

Fresh vaultspec-rag grounding confirms that `rung2SemanticCandidates` is an additive browser tier over the existing Pagefind/lexical controller, while the existing Python miss-rate evaluator models only the precompiled lexical tiers. `dev/docs/terminology/_rung2_evaluation.py` mirrors the validated bundle's covered-token float32 pooling, dequantization, cosine floor, runner-up abstention, bridge ranking, and top-five cap with explicit policy inputs, but it does not compose Pagefind/lexical results or compare unquantized and int8 top-five preservation. It is therefore a safe measurement primitive, not evidence that P02.S07 is complete, and the plan row remains unchecked.

### composition-seam | low | PASS within the source-only boundary

The follow-up composition seam accepts only explicitly supplied lexical observations and the already validated semantic result. Its comparator mirrors the RAG-grounded browser contract for cross-tier direct-match precedence, tier ordering, semantic score/weight ordering, and deterministic ties, then deduplicates record ids and preserves the browser result cap. Source-shape validation rejects semantic rows carrying lexical identity. The seam performs no Pagefind access, artifact loading, acceptance adjudication, or report generation. This is a bounded source improvement; P02.S07 remains open until real Pagefind evidence, the accepted artifact/config, and the authorized post-Rung-2 measurement exist.

### coverage-evidence | low | PASS within the source-only boundary

Fresh vaultspec-rag grounding over the evaluator, browser semantic seam, matrix query-token rows, acceptance contract, and P02.S04/P02.S07 records found that per-query coverage counts existed without an aggregate evidence object. `Rung2CoverageEvidence` and `aggregate_rung2_coverage` now validate the row partition and token arithmetic, reject zero-token or over-covered rows, report full/zero/below-threshold query counts and aggregate coverage, and bind the evidence to the exact validated matrix and bundle identities. The primitive performs no I/O and makes no release decision. P02.S07 remains open pending an authorized full-ladder measurement and accepted artifact evidence.

## Recommendations

Retain the primitive as a source-only seam with no release or acceptance authority. When a real accepted bundle/config exists, add the authorized full-ladder composition and independently measured float32-versus-int8 top-five comparison before committing the post-Rung-2 report or closing P02.S07.
