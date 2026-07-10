---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S41'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the 353<-322 per-member aggregation bindings using per_grupo_member grouping and sum aggregation

## Scope

- `src/aeat/_data/registry/aeat/modelos/353/revisions/2008-y-siguientes/bindings/0002-bindings.toml`

## Description

- Rebaseline stale-open M353 aggregation-binding row against the current registry tree.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M353 binding file.
- Update the plan row to the actual per-member aggregation binding surface.

## Outcome

- `0002-bindings.toml` for M353 declares the `modelo-353-prev-322-*` bindings with `grouping = "per_grupo_member"` and `aggregation = { op = "sum" }`.
- This satisfies the landed 353<-322 per-member aggregation mechanism.
- No product code changed in this step.

## Notes

- This does not claim a different aggregation source or a month-wrap carry.
