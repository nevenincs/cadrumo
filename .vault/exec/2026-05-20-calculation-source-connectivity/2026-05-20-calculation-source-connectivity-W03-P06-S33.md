---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S33'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Add region field to Renta deductibility context when category profiles require it

## Scope

- `src/aeat/domain/renta/_ledger_expenses.py`

## Description

Add an optional `residence_ccaa: CCAA | None = None` field to `RentaDeductibilityContext` (strict-frozen, default `None`), importing `CCAA` through the domain contribuyente facade. The field reuses the one residence-comunidad axis the autonomic-scale bindings already consume.

## Outcome

The region axis now exists on the deductibility context, optional and inert for the general expense path. Landed in commit `1ca532e93a`. A domain test pins the field defaults to `None` and accepts a member. ruff / ruff format / ty clean; pyright clean on the added code.

## Notes

Implements decision D1-A of the proposed ADR `2026-07-04-renta-region-deductibility`. No behaviour change: LIRPF arts. 28-30 base-imponible deductibility is state law and does not vary by comunidad, so the field is inert until a territorial-regime override is declared.
