---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S10'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Evidence Roundtrip Fixture

## Scope

Step `P03.S10`.

## Description

- Replaced negative evidence fixture amounts with positive magnitudes.
- Preserved `direction="outgoing"` as the authoritative flow field.
- Verified strict encrypted revision roundtrip equality.
- Tightened the Renta ledger aggregation helper so it consumes canonical non-negative magnitudes instead of normalizing negative inputs with `abs()`.

## Outcome

Ledger filing evidence roundtrips with absolute native and EUR amounts, and the calculation consumer rejects non-canonical negative ledger inputs.

## Notes

No legal or source reference fields were removed.
