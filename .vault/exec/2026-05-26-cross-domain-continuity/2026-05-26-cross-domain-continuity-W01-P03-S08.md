---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:562d0b3691ebddaf22b9aaf3aff77300fb7ff65dafe63ca378e0eb45d5dd1833'
step_id: 'S08'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# wrap _patch_from_options and update_manual_transaction_fields call inside ledger_update in a try/except ValidationError as exc: raise _ledger_validation_bad(exc) from exc mirroring the pattern already in ledger_classify

## Scope

- `surfaces field-combination errors as operator-readable refusals instead of the opaque boundary message`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Reconciled the historical ledger validation work to the Wave-1 commit review.
- Confirmed `aff4a4c7e` covers the per-verb validation discriminator series.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S09 through S12; each row receives its own record.
