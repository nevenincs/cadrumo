---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S443'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S443 - Close AFR-295 for modelo selectors

Scope: close `AFR-295` for `src/aeat/application/modelo/_selectors.py` with signals `active-profile` and `manifest-bucket`; target `manifest-discovery`.

## Description

- Audited selector request, candidate, resolution, and calculation-revision selection models.
- Confirmed active bucket selection delegates to the core active-profile pointer and repository protocols.
- Confirmed selector errors derive from the modelo/core AEAT error hierarchy and are registered centrally.
- Closed `W18.P38.S443` and updated the `AFR-295` register status to `closed`.

## Outcome

`AFR-295` is closed as `manifest-discovery`. The module selects existing work-unit and calculation-revision records through repository abstractions; it does not own secure-object repository construction, storage routing, raw environment reads, or direct persistence.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_selectors.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/core/errors/tests/test_registry.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S443.
