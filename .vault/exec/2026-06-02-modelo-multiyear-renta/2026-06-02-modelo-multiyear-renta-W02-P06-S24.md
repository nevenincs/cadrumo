---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S24'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M100 general-base negative carry prior-year binding from previous_filing casilla 1391 into current-year casilla 1388 per A4-M100

## Scope

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0020-renta-2024-base-liquidable-negativa-anterior.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/0048-renta-2025-base-liquidable-negativa-anterior.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/1332-1388.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/1387-1388.toml`

## Description

- Rebaseline stale-open M100 registry-binding row against the current registry tree.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of M100 binding and casilla files.
- Update the plan row to the actual M100 general-base negative-saldo binding surface.

## Outcome

- The current registry carries prior-year M100 casilla `1391` into current-year casilla `1388` through `previous_filing` bindings for the 2024 and 2025 Renta revisions.
- This satisfies the landed A4-M100 general-base negative-saldo carry wiring needed by the current enrollment test.
- No product code changed in this step.

## Notes

- This does not claim capital-loss, savings-base `0441` family, deductions, four-year expiry, or integration-subtract completeness.
