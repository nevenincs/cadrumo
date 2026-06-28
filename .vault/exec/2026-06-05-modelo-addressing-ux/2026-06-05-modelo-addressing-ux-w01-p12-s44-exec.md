---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S44'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P12.S44 public modelo addressing facade exports

Scope:
- `src/aeat/application/modelo/__init__.py`

## Description

- Export typed modelo addressing contracts from the top-level modelo application package.
- Export visible/exact work-target resolution and projection helpers from the top-level modelo application package.
- Keep CLI and external consumers aligned to `aeat.application.modelo` instead of private implementation modules.
- Sort the package `__all__` with Ruff after adding the public names.

## Outcome

The centralized modelo addressing contracts and helpers are now available through the public application facade. Future CLI migration work can import from `aeat.application.modelo` while `_work_addressing.py` remains a private implementation module.

## Notes

- `uv run --no-sync ruff check src/aeat/application/modelo/__init__.py src/aeat/application/modelo/_work_addressing.py` passed.
- Public import smoke test from `aeat.application.modelo` passed.
- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py -q` passed with 13 tests.
- The same `__init__.py` file already carried registry discovery export changes from another slice; this step did not revert them.
- A code-review audit entry was appended to `2026-06-05-modelo-addressing-ux-code-review-audit`.
