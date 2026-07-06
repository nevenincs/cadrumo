---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S54'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M200 BIN stock carry binding copying prior pending BIN into the current-year binding surface

## Scope

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/relations.toml`

## Description

- Rebaseline stale-open M200 BIN-binding row against the current registry tree.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M200 relation registry.
- Update the plan row to the actual BIN stock carry binding surface.

## Outcome

- The M200 registry declares `modelo-200-2024-rel-self-bin-pendiente-anterior`, copying prior casilla `00671` to the current BIN-pending binding.
- This satisfies the landed BIN stock carry binding surface.
- No product code changed in this step.

## Notes

- This does not claim full elective application into final cuota as part of the binding itself.
