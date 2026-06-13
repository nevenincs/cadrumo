---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S42'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P12.S42 bidirectional work target facade

Scope:
- `src/aeat/application/modelo/_work_addressing.py`

## Description

- Add a `ModeloWorkTarget` union for visible filing targets, exact work-unit targets, and the legacy-compatible address shape.
- Add `work_address_for_modelo_target` as the single coercion point from typed targets to selector input.
- Add `resolve_modelo_work_target` and `resolve_modelo_work_unit_id` to resolve visible or exact targets through the shared selector boundary.
- Add `project_modelo_work_unit` and `project_modelo_work_target` to project exact work-unit identity back into visible filing metadata.
- Keep all resolution on the existing application selector path and avoid new persistence or CLI-local policy.

## Outcome

Visible filing targets can now resolve to authoritative work-unit IDs through one application facade, and exact work-unit targets can be projected back to visible modelo, filing year, period, registry revision, lifecycle state, and pointer metadata.

## Notes

- `uv run --no-sync ruff check src/aeat/application/modelo/_work_addressing.py` passed.
- `uv run --no-sync python -m py_compile src/aeat/application/modelo/_work_addressing.py` passed.
- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py -q` passed with 13 tests.
- Code review found no blocking issue, but reinforced that `W01.P12.S44` must export these names through `src/aeat/application/modelo/__init__.py` before consumers use them.
