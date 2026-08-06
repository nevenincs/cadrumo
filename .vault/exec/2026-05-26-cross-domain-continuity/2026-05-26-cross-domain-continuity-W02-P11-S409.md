---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:ec7e8a11b035b461f41c00a359531a0ace96d0701e472cad82f47cf129ac630d'
step_id: 'S409'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-S325-A review remaining attribution-entity exclusions on payer-fact and informative modelos

## Scope

- `closed by ac11025c1: canonical payer-fact entity set now includes attribution entities for M115/M180/M349/M347 when the matching payer`
- `trade`
- `or threshold fact is present`
- `absent facts remain INCOMPLETE instead of entity-excluded`
- `M349 and M347 gained direct RIVA/RGAT legal refs`
- `verified by 32 registry applicability tests`
- `68 overview applicability tests`
- `ruff`
- `diff check`
- `and official source review`
- `ty remains blocked by the shared-tree missing stubs directory`
- `src/aeat/domain/calculations/registry/_applicability.py`

## Description

- Reconciled the payer-fact applicability correction to the plan's cited landing.
- Confirmed `ac11025c1` supplied the implementation and focused verification.
- Added this per-step execution record without changing production sources.

## Outcome

The plan's explicit landing evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

The original plan row records the official-source and test evidence.
