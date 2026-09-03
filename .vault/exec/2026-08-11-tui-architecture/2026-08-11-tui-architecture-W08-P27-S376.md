---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:fcb670c6ddde14fcd55bce44ca787d52cb8a653125df71f500966070bafb66f0'
step_id: 'S376'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Remove concrete-host narrowing and whole-application exits from the declaration picker, review, workspace, and editor route chain

## Scope

- `src/cadrumo/entrypoints/tui/modelo/`

## Changes
- `M` `src/cadrumo/entrypoints/tui/modelo/view/work_select.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/work_review.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/overview.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/inputs.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/results.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/provenance.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/verification.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/filing.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/tests/`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s376-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/modelo/tests` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/modelo` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/modelo` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/modelo` -> `pass`
