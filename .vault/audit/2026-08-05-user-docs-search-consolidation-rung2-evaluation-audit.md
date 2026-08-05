---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:238baec10ca1dd95ac29778ee079521c5f1e99ed223d7672880f67e1f974abd0'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
  - "[[2026-08-05-user-docs-search-consolidation-source-contract-reference]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace user-docs-search-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backticks: `src/module.py`. -->

# `user-docs-search-consolidation` audit: `Rung-2 evaluator source review`

## Scope

Audit the new source-only Rung-2 held-out measurement primitive against the accepted ADR, the source contract reference, the browser semantic implementation, the validated bundle/quantized matrix models, and the existing pre-Rung-2 evaluator. The review is intentionally source-only: tests, builds, artifacts, runtime probes, and deployment are out of scope under the current operator boundary.

## Findings

### rung2-evaluator | medium | The primitive is semantic-tier measurement, not the full P02.S07 ladder report

Fresh vaultspec-rag grounding confirms that `rung2SemanticCandidates` is an additive browser tier over the existing Pagefind/lexical controller, while the existing Python miss-rate evaluator models only the precompiled lexical tiers. `dev/docs/terminology/_rung2_evaluation.py` mirrors the validated bundle's covered-token float32 pooling, dequantization, cosine floor, runner-up abstention, bridge ranking, and top-five cap with explicit policy inputs, but it does not compose Pagefind/lexical results or compare unquantized and int8 top-five preservation. It is therefore a safe measurement primitive, not evidence that P02.S07 is complete, and the plan row remains unchecked.

### composition-seam | low | PASS within the source-only boundary

The follow-up composition seam accepts only explicitly supplied lexical observations and the already validated semantic result. Its comparator mirrors the RAG-grounded browser contract for cross-tier direct-match precedence, tier ordering, semantic score/weight ordering, and deterministic ties, then deduplicates record ids and preserves the browser result cap. Source-shape validation rejects semantic rows carrying lexical identity. The seam performs no Pagefind access, artifact loading, acceptance adjudication, or report generation. This is a bounded source improvement; P02.S07 remains open until real Pagefind evidence, the accepted artifact/config, and the authorized post-Rung-2 measurement exist.

## Recommendations

Retain the primitive as a source-only seam with no release or acceptance authority. When a real accepted bundle/config exists, add the authorized full-ladder composition and independently measured float32-versus-int8 top-five comparison before committing the post-Rung-2 report or closing P02.S07.
