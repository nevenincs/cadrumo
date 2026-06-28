---
tags:
  - '#exec'
  - '#core-authority'
step_id: S10
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P03.S10 — CalculationRevisionNotFoundError -> CoreNotFoundError

## Change

`CalculationRevisionNotFoundError(ModeloError, KeyError)` →
`(ModeloError, CoreNotFoundError)`.

CoreNotFoundError provides both CoreError and KeyError co-inheritance.
MRO: CalculationRevisionNotFoundError -> ModeloError -> CoreNotFoundError
     -> CoreError -> AeatError -> KeyError -> LookupError -> Exception.

## Deviation from plan

Plan said "second domain NotFoundError subclass in src/aeat/domain/". Actual
target per ER-03 semantic pair: CalculationRevisionNotFoundError is in
application/modelo/_actions.py.

## Verification gate

`pytest src/aeat/application/modelo/ -q` — exit code 0 (background task beu17quh2).

## Commit

`f7dec82b2` — feat(errors): W02.P03.S10 CalculationRevisionNotFoundError -> CoreNotFoundError
