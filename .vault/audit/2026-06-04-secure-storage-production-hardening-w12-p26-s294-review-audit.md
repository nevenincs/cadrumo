---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S294]]'
---

# `secure-storage-production-hardening` `W12.P26.S294` Review

## S294-001 | PASS | Modelo registry errors are centrally enrolled

The application error registry now declares stable codes for modelo projection, comparison, work-selector, calculation-revision-selector, and work-addressing errors. The registry rows use stable `errors.*` locale keys and operator suggestions instead of ad hoc plaintext-only failures.

## S294-002 | PASS | New local exception roots derive from `AeatError`

The projection family derives from `AeatError`, and the work-addressing not-found/year-mismatch errors derive from the modelo error family while preserving `LookupError` / `ValueError` catch compatibility. The registry enforcement gate confirms every registered code maps to exactly one imported `AeatError` subclass.

## S294-003 | PASS | Locale catalogue is canonical

All new registry message keys were scaffolded and translated through `python -m aeat.locales`; locale audit and scaffold check both passed for `en`, `es`, `ca`, and `hu`.

## S294-004 | PASS | Validation

- `uv run --no-sync ruff check ...`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/application/modelo/test_selectors.py src/aeat/entrypoints/cli/test_modelo_projection.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- `PYTHONPATH=src uv run --no-sync python -m aeat.locales scaffold --check`
- `PYTHONPATH=src uv run --no-sync python -m aeat.locales audit`

Disposition: close `AFR-192`.
