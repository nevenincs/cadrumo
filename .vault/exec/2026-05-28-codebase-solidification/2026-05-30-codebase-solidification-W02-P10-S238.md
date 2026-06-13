---
step_id: S238
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S238

**Relocate `CLASSIFIED_BY_MANUAL` to `aeat.core.external_constants`; full caller migration.**

## Approach

Full migration chosen over re-export shim. `aeat-architecture-boundaries.md` forbids shims and re-exports.

## Files touched

- `src/aeat/core/external_constants.py` — added `CLASSIFIED_BY_MANUAL: Final[str] = "manual"` in the module-level constants block.
- `src/aeat/application/ledger/_models.py` — removed local definition and `Final` import; added `CLASSIFIED_BY_MANUAL` to the `external_constants` import.
- `src/aeat/application/ledger/__init__.py` — moved import source from `_models` to `...core.external_constants`.
- `src/aeat/application/ledger/_actions.py` — added `CLASSIFIED_BY_MANUAL` to the `external_constants` import; removed from `_models` import.
- `src/aeat/entrypoints/cli/_ledger.py` — added `CLASSIFIED_BY_MANUAL` to `external_constants` import; removed from `application.ledger` import.
- `src/aeat/application/ledger/test_models.py` — updated identity test to assert against `external_constants` origin.

## Caller count

5 caller sites migrated (1 definition removed, 4 imports redirected).

## Outcome

135 tests pass in the targeted scope.
