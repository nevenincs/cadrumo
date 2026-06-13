---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S137'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P19.S137 backend adjacent command orchestration

Scope:
- `src/aeat/application/modelo`
- `src/aeat/entrypoints/cli`

## Description

- Add backend-owned modelo projection and comparison services.
- Move `modelo project` aggregation, profile binding merge, M100 registry calculation, extrapolation, and result construction out of the CLI command body.
- Move `modelo compare` revision selection, registry metadata lookup, delta calculation, provenance transfer, and section grouping out of the CLI command body.
- Preserve existing backend service ownership for export, reconciliation, and taxation comparison command orchestration.
- Remove duplicated projection error-code registry entries that became invalid after projection refusals were kept as local application exceptions.

## Outcome

Implemented:

- `src/aeat/application/modelo/_projection.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_projection.py`
- `src/aeat/core/errors/registry/_application.py`

Verification:

- `uv run --no-sync python -m py_compile src/aeat/application/modelo/_projection.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo_projection.py src/aeat/core/errors/registry/_application.py`
- `uv run --no-sync ruff check src/aeat/application/modelo/_projection.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo_projection.py src/aeat/core/errors/registry/_application.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_projection.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_compare.py -q`

## Notes

- `uv run` without `--no-sync` attempted to reinstall a locked `torch` wheel during RAG execution; focused verification used `--no-sync` to avoid mutating the shared virtual environment.
- The M100 projection backend now supplies the no-prior-filing baseline for `renta-{year}-base-liquidable-negativa-general-anterior`, matching the registry's required previous-filing binding for casilla 1388.

## Addendum: taxation natural-key orchestration

- Added `compare_taxation_for_work_address` in `src/aeat/application/modelo/_taxation_comparison.py`.
- Exported the address-based taxation service through `src/aeat/application/modelo/__init__.py`.
- Updated `work compare-taxation` in `src/aeat/entrypoints/cli/_modelo.py` so the CLI builds the operator address, calls the backend service, and renders the typed result; work-unit resolution no longer happens in the command body.
- Registered projection service errors and filled projection/compare locale messages needed by the new application service import path.

Verification addendum:

- `.venv\Scripts\python.exe -m py_compile src/aeat/application/modelo/_taxation_comparison.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py`
- `.venv\Scripts\ruff.exe check src/aeat/application/modelo/_taxation_comparison.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py --select F401,F821,E501`
- `.venv\Scripts\pytest.exe src/aeat/application/modelo/test_taxation_comparison.py src/aeat/entrypoints/cli/test_modelo_projection.py src/aeat/entrypoints/cli/test_modelo_compare.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_export_verb.py -q` - 29 passed.
