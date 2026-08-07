---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:02ad793dc1330a924e313a6c998165c7bb92ef4eae2643e99ee4d86f4b53a66c'
step_id: 'S33'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S33

## Outcome

Ruled, and the ruling is now visible in the set itself: the exclusion set enumerates BOTH the apartado Dos carve-outs AND the apartado Uno territorial-scope cases, and records which is which.

## The ambiguity this Step named

Six members were art. 163 duodecies **Dos** letters and one was a **Uno** scope case, with nothing in the code distinguishing them. A reader could not tell whether the set was "the Dos list" (making the Uno member a mistake) or "everything outside the regime" (making the Dos list incomplete).

## The ruling

`_CASH_ACCOUNTING_EXCLUDED_CATEGORIES` (`application/aggregation/_iva_ledger.py:1098`) is now explicitly two-part, under two comments: the six apartado Dos carve-outs, then `OPERACION_NO_SUJETA` and `DOMESTIC_NOT_SUBJECT` under "apartado Uno scope: not subject in the TAI".

So the set means "everything outside the regime", reached by two distinct legal routes, and the comment records which clause puts each member there. A future member can now be added under the right heading instead of appended to an undifferentiated list.

The second not-subject member the ruling admits is the subject of `S43`; the OSS-path check that had to precede it is `S34`.
