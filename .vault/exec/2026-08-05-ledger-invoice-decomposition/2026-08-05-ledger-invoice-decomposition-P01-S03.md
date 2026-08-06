---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c4492bfc44818f16922c3b48fa427e4ff9a10cd30a53e30066825d411bc6fdd8'
step_id: 'S03'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched

## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`

## Description

- Rename the renta and impatriado fact `gross_income_sum` to `cash_received_sum` in the selector literals, the accepted-fact frozensets, the aggregate dispatch, and every docstring naming it.
- Sweep the stale Modelo 130 fragment comment that named the old fact as a live path.
- Leave the Modelo 210 member untouched.

## Outcome

Landed in commit `73ea70ea41`.

The name now states what the code computes: the absolute raw transaction amount, the cash the bank credited. That figure is net of any retencion practicada and possibly IVA-inclusive, so it is neither gross of retencion nor IVA-exclusive - the old name asserted a property the implementation never had, which is why the divergent default survived review. A reader checking the default read a name that sounded correct.

Modelo 210's identically-named member is deliberately NOT renamed: it sums the DECLARED classification amount, not raw cash, so the name is accurate there. Re-verified at HEAD that it is the only committed registry binding using the old spelling, and that it routes through the IRNR selector, a different class.

Registry impact of the rename: zero. No renta or impatriado binding used the member.

## Notes

The rename is a deletion-rename with no alias, per the pre-release no-legacy-compatibility posture.

The M130 fragment comment claiming the operator "selects one binding or the other via the fact selector" was corrected while sweeping: the binding it pointed at is the ingresos-integros one, not a cash-summing path, so the comment named a route that did not exist.
