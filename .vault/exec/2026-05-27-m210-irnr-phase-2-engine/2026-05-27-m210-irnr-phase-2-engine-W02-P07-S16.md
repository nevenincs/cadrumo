---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:4d7be45ae1fcc48117e6c0b6eb31186f3ab72f9bdc057d427b12351c5492d08f'
step_id: 'S16'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# architect-2 selects classifier-based vs predicate-based shape, determining the S10/S11 and S13/S14 sites (if predicate-based, author a new operator following the S376/S377/S378 pattern, otherwise close as a no-op affirming the classifier-based Steps)

## Scope

- `src/aeat/application/modelo/_verification_predicates.py`

## Description

- Reconcile the recorded architect verdict on the source-jurisdiction gate shape.
- Confirm that the classifier-based option is selected and that no registry-predicate operator is required for this work.

## Outcome

The classifier-based shape is selected. The source-jurisdiction research and the cross-domain continuity closing review reject a registry predicate because it loses per-row provenance and produces opaque aggregate refusals. The completed M151 implementation follows this shape; a future M210 implementation must use the same classifier-and-typed-issue contract.

## Notes

This is an architecture-decision reconciliation record. No new production code was authored.
