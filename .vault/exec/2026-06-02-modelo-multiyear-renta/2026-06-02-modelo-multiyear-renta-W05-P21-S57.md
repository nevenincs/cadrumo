---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S57'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M202 cuota-base ejercicio anterior bindings from prior Modelo 200 cuota liquida for 2P and 3P

## Scope

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/0003-modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior.toml`
- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/relations/0004-modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p.toml`

## Description

- Rebaseline stale-open M202 prior-cuota binding row against the current registry tree.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M202 binding and relation files.
- Update the plan row to the actual cuota-base ejercicio anterior binding surface.

## Outcome

- The M202 registry binds prior Modelo 200 cuota liquida `DP200014B:00592` into the M202 2P/3P cuota-base surface.
- The companion relation covers the 2P/3P prior-year path in the 2025-y-siguientes revision.
- No product code changed in this step.

## Notes

- This must not be described as cuota integra; the landed source is prior M200 cuota liquida.
