---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S134'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P19.S134 natural-key lifecycle orchestration extraction

Scope:
- `src/aeat/application/modelo`

## Description

- Add backend service for resolving or creating a work unit by visible filing target.
- Move visible-target resume/create decision and registry revision resolution out of `work create`.
- Move registry revision year-coverage validation out of `_modelo.py`.
- Keep CLI exact-ID and natural-key argument parsing as boundary work only.

## Outcome

Implemented in `src/aeat/application/modelo/_work_addressing.py`:

- `ModeloWorkAddress`
- `ModeloWorkEnsureResult`
- `resolve_registry_revision_for_work_target`
- `ensure_modelo_work_unit_for_visible_target`
- `resolve_modelo_work_address_unit`
- `resolve_modelo_calculation_revision_address`

Removed dead CLI registry target validation helpers from `_modelo.py` after backend extraction.

Verification:

- `uv run ruff check src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_payloads.py`
- `uv run python -m py_compile src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_payloads.py`
- `uv run pytest src/aeat/application/modelo/test_selectors.py src/aeat/application/modelo/test_export.py -q`

## Notes

- The CLI still contains substantial business logic in calculate/project/compare and remains subject to W06.P19.S137/S139 and W06.P20 decomposition.
