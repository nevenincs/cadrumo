---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S42'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Define inventory resolver adapter boundaries without enrolling calculations

## Scope

- `src/aeat/application/aggregation/_source_inventory.py`

## Description

Add `application/aggregation/_source_inventory.py`: `InventorySourceReadinessResolver`, implementing the source-mesh resolver shape (`resolver_id`, `owned_sources = ()`, `resolve`) but NOT enrolled in `merge_source_resolutions`. Its `resolve` reads `inventory_source_readiness()` and returns an empty resolution carrying exactly one `source_domain_not_ready` blocked-readiness diagnostic (reusing the reason member added in S40).

## Outcome

The inventory source surface is provisioned as a resolver-adapter boundary that refuses visibly and enrolls nothing (owns no `BindingSourceKind`). Landed in commit `7c15ee0184`. Gates clean.

## Notes

Mirrors the fincas resolver of S40; the `inventory` diagnostic `source_kind` is a free string outside the `BindingSourceKind` taxonomy, so it cannot enter the live mesh source sets.
