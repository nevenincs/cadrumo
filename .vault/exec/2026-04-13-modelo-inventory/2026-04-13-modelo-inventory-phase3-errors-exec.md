---
name: 2026-04-13-modelo-inventory-phase3-errors
description: Phase 3 execution record — registry error hierarchy (#108)
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
---

# phase 3 — error hierarchy

## delivered

- `_errors.py` — `ModeloRegistryError` (base, inherits `AeatError`),
  `UnknownModeloError` (carries offending code string),
  `RegistryIntegrityError` for import-time structural violations.
- `test_codes.py` — added subclass smoke asserting the error classes
  import from `aeat.domain.modelos._errors` and chain through `AeatError`.

## gate outcomes

- `just lint`, `just typecheck`, `just hooks` — passed.
- `just test` — 740 passed, 1 skipped, 23 deselected.

## deviations

None.

## commit

`b2154d3 feat(models): error hierarchy for registry lookups (#108)`
