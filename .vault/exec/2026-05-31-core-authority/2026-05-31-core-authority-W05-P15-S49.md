---
step_id: S49
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W05.P15.S49 — move CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE to core/external_constants.py (RENAME-014)

## Files modified

- `src/aeat/core/external_constants.py` — added `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE: Final[str]` with doc comment
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` — removed local declaration; added import from `core.external_constants`; retained `_DIAGNOSTIC_NAMESPACE` private alias
- `src/aeat/application/auth/test_diagnostics.py` — updated import from adapters to `core.external_constants` (fixes Rule 2 violation)
- `src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` — updated import from `_clave_movil` to `core.external_constants`

## Commit

`ac8731a08` — refactor(auth): move CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE to core/external_constants.py (RENAME-014 W05.P15.S49)

## Before / After

- Before: declared in `_clave_movil.py`; `application/auth/test_diagnostics.py` imported from `adapters` (Rule 2 violation)
- After: canonical in `core/external_constants.py`; all consumers import from core; adapter retains `_DIAGNOSTIC_NAMESPACE = CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` as private alias; `adapters/auth/__init__.py` re-export continues to work transitively

## Test run

```
pytest src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/persistence/storage/test_namespace_registry.py -q
# → 30 passed
```
