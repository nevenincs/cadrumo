---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:553c9d2c17cd4f2da53258327ae00fab136f13fcfbc24b399ec8845b8afd455b'
step_id: 'S325'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-MANUEL-C M303/M390/M111 applicability over-restrictive for attribution_entity

## Scope

- `closed by 7981cd3d7: canonical _MODELO_APPLICABILITY_RULES now treats attribution entities as IVA-obliged for M303/M390 when iva_regime is GENERAL or SIMPLIFICADO and as M111/M190 payer-fact candidates when employee/professional withholding facts are present`
- `added positive and negative applicability tests plus overview parity guards`
- `verified by 24 registry applicability tests`
- `61 overview applicability tests`
- `4 canonical-source tests`
- `ruff`
- `and diff check`
- `ty remains blocked by the shared-tree missing stubs directory`
- `src/aeat/domain/calculations/registry/_applicability.py`

## Description

- Reconciled the attribution-entity applicability correction to the plan's cited landing.
- Confirmed `7981cd3d7` supplied the implementation and focused verification.
- Added this per-step execution record without changing production sources.

## Outcome

The plan's explicit landing evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

The original plan row records the scoped test and lint evidence.
