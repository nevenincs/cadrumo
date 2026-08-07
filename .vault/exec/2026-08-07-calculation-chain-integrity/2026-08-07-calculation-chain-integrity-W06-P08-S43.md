---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:77c01b389b16051e6818731a0b4d6fa1ecf6d32d5954c5c453b3a82c15cfd28c'
step_id: 'S43'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S43

## Outcome

Landed with the mutation proof the Step demands, now that `S34` confirmed the OSS scope refusal is correct.

## The addition

`DOMESTIC_NOT_SUBJECT` joins `OPERACION_NO_SUJETA` under the apartado Uno heading in `_CASH_ACCOUNTING_EXCLUDED_CATEGORIES` (`application/aggregation/_iva_ledger.py:1108-1109`). Both are not-subject in the TAI and therefore outside the regime by art. 163 duodecies Uno scope rather than by a Dos carve-out.

## Why the Step insisted on a proof

A set-membership edit is the shape most likely to red nothing: adding a member to a frozenset changes no signature, breaks no caller, and passes every existing test unless one specifically exercises that member. The test docstring records that `DOMESTIC_NOT_SUBJECT` was previously absent, so the edit had to be shown to bite rather than assumed to.

## The proof set

Three tests in `application/aggregation/tests/test_iva_cash_accounting.py`, and the second two are what make the first meaningful:

- `test_both_not_subject_categories_are_outside_the_cash_accounting_regime` is parametrised over both members, so the new one is exercised by name rather than by the set's mere existence.
- `test_an_exempt_domestic_supply_still_enters_the_cash_accounting_regime` is the positive control. Without it, an exclusion that had swallowed every category would satisfy the test above.
- `test_a_not_subject_row_outside_the_regime_is_not_refused_by_this_gate` carries `S34`'s finding forward as an executable guarantee, so a later broadening of the refusal past the regime boundary reddens here.
