---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S444'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S444 - Close AFR-296 for modelo work addressing

Scope: close `AFR-296` for `src/aeat/application/modelo/_work_addressing.py` with signals `active-profile` and `manifest-bucket`; target `manifest-discovery`.

## Description

- Audited visible-target and exact-id addressing models for modelo work-unit commands.
- Confirmed work-address resolution delegates to central selector services and repository-owned runtime custody.
- Confirmed period/revision errors derive from the modelo/core AEAT error hierarchy and are registered centrally.
- Closed `W18.P38.S444` and updated the `AFR-296` register status to `closed`.

## Outcome

`AFR-296` is closed as `manifest-discovery`. The module projects and resolves operator-visible work addresses over existing work-unit and calculation-revision records without owning storage routing or persistence.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_selectors.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/core/errors/tests/test_registry.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S444.
