---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:47ce5e29f6ba5445e76bc0b969c31208ba1295cbdb8811a2d8f32775ecf95677'
step_id: 'S227'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# defer Modelo 220 group values as an ingress-blocked evidence decision

## Scope

- `.vault/research/2026-08-25-source-casilla-integration-modelo-220-group-value-source-grounding-research.md`
- `.vault/adr/2026-08-25-source-casilla-integration-m220-source-owner-deferral-adr.md`
- `.vault/exec/2026-08-22-source-casilla-integration/2026-08-22-source-casilla-integration-W06-P20-S227.md`
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md`
- `.vault/index/source-casilla-integration.index.md`

## Description

- Attest the 2024 AEAT design hash
  `a8f398dd42db0b1142d5f2e98bf3a60d79069e31d63af32001373f459fee4f2e` and
  2025 design hash
  `69c3a234e96eb4485a31c65209348bbcede0a49a8c143223c952000784f3f2df` as
  distinct year-scoped target evidence.
- Preserve the composite group/member source grain, including an explicit
  absent-versus-inapplicable-versus-zero state, rather than collapsing it to a
  header or total.
- Record the accepted model-scoped ADR that owns the ingress-blocked
  disposition, accountable owner, and reopening predicate.
- Add no census row, producer, binding, resolver, lifecycle, layout, or export
  route.

## Outcome

The accepted M220 source-owner deferral ADR owns the bounded
`ingress_blocked` disposition and reopening predicate. The 2024 and 2025
designs remain separate evidence eras. No M220 producer key, binding, casilla
change, layout, source-mesh route, or census disposition was created.

## Notes

- The model-scoped ADR is the sole home for M220 normative deferral language;
  this execution record only attests the accepted decision and its no-runtime,
  no-census boundary.
- Semantic RAG initially selected binary workbook blobs, whose renderer cannot
  decode them as UTF-8. Discovery was narrowed to text registry and filing
  surfaces; the official workbook evidence was read through its hash-pinned
  extracted text and source catalogue.
