---
tags:
  - '#exec'
  - '#core-authority'
step_id: S22
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P07.S22 — DELETE-003 ripgrep gate: BLOCKED

## Blocking Condition

The plan's own execution gate "after ripgrep confirms zero callers" was not
satisfied. `DAYS_PER_YEAR` in `src/aeat/domain/fincas/_amortization_ledger.py`
has an active caller at line 101 of the same file, used in the amortization
basis calculation: `basis * ART_23_1_F_RATE * Decimal(income.dias_alquilados) / DAYS_PER_YEAR`.

## Ripgrep Evidence

```
src/aeat/domain/fincas/_amortization_ledger.py:33: DAYS_PER_YEAR: Decimal = Decimal("365")
src/aeat/domain/fincas/_amortization_ledger.py:101: ... / DAYS_PER_YEAR
```

## Resolution

Step left unchecked. No code changes made. Deferred to a future campaign.
