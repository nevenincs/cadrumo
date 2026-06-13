---
step_id: S07
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S07 — IvaCompensationModeloError

## Outcome

Introduced `IvaCompensationModeloError(CoreError)` in the new module
`src/aeat/application/calculations/_errors.py`. Replaced the bare
`ValueError("IVA compensation history only accepts Modelo 303 observations")`
at line 291 of `_iva_compensation_history.py` with the typed domain error.
Registered `REFUSED_IVA_COMPENSATION_MODELO` in
`src/aeat/core/errors/registry/_application.py`.

## Files touched

- `src/aeat/application/calculations/_errors.py` (created)
- `src/aeat/application/calculations/_iva_compensation_history.py` (import + raise replaced)
- `src/aeat/core/errors/registry/_application.py` (ErrorCode entry added)

## Collision check

`git diff` on all three target files returned empty — no non-authored WIP.

## Commit

`0b1518aa7`
