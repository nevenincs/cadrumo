---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Migrate the prorrata_regularizacion deferral from its free-prose comment to a structured annotation citing its accepted 2026-07-01 IVA ADR and the provisional-carry plus Q4 regularisation trigger

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Migrate the `prorrata_regularizacion` deferral from its free-prose comment to a structured target citing `2026-07-01-iva-complexity-hardening-scope-adr` and the provisional-carry + Q4 regularisation promotion trigger (iva_compensation_annual_partition precedent).

## Outcome

prorrata regularización is governed with its owning IVA ADR and dependency trigger.

## Notes
