---
tags:
  - '#exec'
  - '#core-authority'
step_id: S03
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P02.S03 — CoreError catch-order contract test

## Decision: AeatError as structural root

AeatError is the project-wide root with `__init_subclass__` registry
enforcement already in place. CoreError exists as `AeatError -> CoreError`
in `core/errors/__init__.py`. No new `_base.py` file was needed; the plan's
reframe clause applies — "if AeatError is the existing root, W02 is reframed
as making AeatError the structural-enforcement root".

## Files touched

- `src/aeat/core/errors/test_core_error_root.py` — created (76 lines)

## Verification gate

`pytest src/aeat/core/errors/test_core_error_root.py -x -q` — 4 passed.

## Commit

`d93413869` — feat(errors): W02.P02.S03 CoreError catch-order contract test
