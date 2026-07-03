---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Migrate the bienes_inversion_regularizacion deferral to a structured annotation citing its accepted 2026-07-01 ADR and the prorrata-definitiva-source-lands dependency trigger

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Migrate the `bienes_inversion_regularizacion` deferral to a structured target citing `2026-07-01-iva-bienes-inversion-regularizacion-adr`, with `promotion_depends_on = PRORRATA_REGULARIZACION` (it consumes the same definitive percentage).

## Outcome

bienes-inversión regularización is governed and mechanically dependency-linked to prorrata landing.

## Notes
