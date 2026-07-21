---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S37'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# record the deferred prorrata especial per-input apportionment and the art-103.Dos.2 +10% mandatory-especial comparison advisory as an honest deferred Step behind the from-birth regime schema slot (needs especial to exist first)

## Scope

- `.vault/exec/2026-07-06-cross-period-prorrata/`

## Description

- Re-read the live plan status and confirmed `W06.P09.S37` was the next open step after S36.
- Re-grounded the deferral through semantic search, the cross-period prorrata ADR, the W06 plan row, the register regime enum, and the IVA prorrata domain substrate.
- Confirmed the register has a from-birth `ProrrataRegisterRegime.ESPECIAL` slot, so a future especial entry can land without a schema migration.
- Confirmed the domain substrate already has the legal primitive `is_especial_mandatory`, grounded in the Art. 103.Dos +10 percent comparison constant.
- Recorded the remaining blocker honestly: live per-input prorrata especial apportionment requires ledger/input classification by exclusive deductible use, exclusive non-deductible use, and common use before the Art. 103.Dos.2 advisory can be calculated without fabrication.

## Outcome

- S37 is formally deferred.
- Follow-up: implement the prorrata especial per-input classification and apportionment surface, then wire a non-blocking Art. 103.Dos.2 mandatory-especial comparison advisory against the general-regime deduction.
- Until that lands, the current campaign intentionally ships only the general-regime apportionment and keeps the especial slot as schema capacity, not live behavior.

## Notes

- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\prorrata_register\tests\test_prorrata_register.py src\aeat\domain\iva\tests\test_prorrata.py -n 0` (51 passed).
