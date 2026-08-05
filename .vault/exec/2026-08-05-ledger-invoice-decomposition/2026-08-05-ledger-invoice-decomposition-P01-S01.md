---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:968e2e34f275157603183984663340e2656691bf5535f7e154f39f489280be53'
step_id: 'S01'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Remove the fact default from the renta ledger income selector so an omitting binding fails registry validation loudly

## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`

## Description

- Remove the `fact` default from `_RentaLedgerIncomeSelector` so the field is required.
- Add a before-validator refusing an omitted `fact` with a message naming every accepted fact.
- Rename the family's accepted-fact frozenset to drop its misleading modelo segment, and share it between the refusal message and the build-time invariant so the two can never name different sets.

## Outcome

Landed in commit `73ea70ea41`.

`fact` is required on the renta income selector. A binding that omits it is refused at registry build, and the refusal enumerates the accepted set rather than emitting pydantic's bare "Field required" - the requiredness only helps an author who is told what to choose.

Zero behaviour change, re-verified at HEAD before landing: all six committed renta bindings (four in the M130 cumulative fragment, one each in the M100 2024 and 2025 income fragments) already declare `fact` explicitly.

Test evidence: the income-binding module ran 14 passed, 0 failed (serial). Registry suite at the time of landing: 3543 passed, 2 failed - both attributed to peers and neither in scope (a string-format KeyError on a TOML inline table in a loader-fingerprint test never touched here, and a line-count baseline exceeded by a peer's actively-dirty relation-sources validator).

## Notes

The refusal message needed a before-validator rather than field metadata: pydantic enumerates the accepted members for a WRONG value but says only "Field required" for a MISSING one, so the missing half was the only gap left to close.

A test docstring asserting the removed default ("the selector's own default fact") was corrected in the same commit rather than left standing - a docstring asserting a property the code no longer has is load-bearing for the next reader.
