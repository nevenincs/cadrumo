---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S185'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# register Modelo 390 annual deadline windows filing in January for 2025 and 2026

## Scope

- `src/aeat/_data/registry/aeat/modelos/390.toml`

## Description

- Ground the annual filing rule through the RAG index, the bundled BOE authority, and the current AEAT deadline guidance.
- Inspect the committed Modelo 390 deadline-window registry and resolve both target filing years through the live authority facade.
- Run the dedicated committed-registry and filing-schedule tests plus Ruff.
- Obtain an independent review of the statutory tuples, evidence references, and weekend-handling boundary.

## Outcome

The existing registry already contains the required annual windows: 2025 0A opens on 2026-01-01 and closes on 2026-01-30, while 2026 0A opens on 2027-01-01 and closes on 2027-01-30. Both carry the Modelo 390 BOE and AEAT source references. The dedicated test pins both exact tuples; 23 focused tests and Ruff passed. Independent review found no critical, high, or medium issue, so the stale plan premise is reconciled without a duplicate implementation.

## Notes

The registry records the raw statutory close. The deadline engine separately shifts a weekend or holiday close for operator-facing obligations. A 2027 holiday-calendar record is not bundled, so an adjusted 2027 operational due date is intentionally outside this registry-window reconciliation.
