---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:5b3287a6042aef0ccec47bb7e7e54e64a5cac0d03801478fc6a744e01190c281'
step_id: 'S41'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Define inventory calculation source readiness diagnostics

## Scope

- `src/aeat/application/inventory/_source_readiness.py`

## Description

Add `application/inventory/_source_readiness.py`: an `InventorySourceReadiness` (strict-frozen `ready` / `source_kind` / `reason`) and an `inventory_source_readiness()` returning `ready = False`, because inventory is an application service over profile inventory whose movements and valuations are not persisted through the canonical secure-storage revision boundary. Export the surface from the inventory package facade.

## Outcome

The inventory calculation-source readiness is a context-independent fact the aggregation resolver reads. Landed in commit `7c15ee0184`. Gates clean.

## Notes

Inventory readiness lives at the application layer (not domain) because inventory is an application service, unlike the fincas domain in S39. Implements the inventory half of the ADR Phase 8 deferral: NOT ready, so the surface refuses visibly.
