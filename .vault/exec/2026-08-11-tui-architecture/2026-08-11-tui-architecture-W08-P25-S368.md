---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:2dd81d1c0aff0b1e00a3544bcdb459994e0f39f1c79275d1aaa83d1a5b6211a2'
step_id: 'S368'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define typed workbench search results and a cross-domain query service that preserves source, natural address, status, and admission

## Scope

- `src/cadrumo/application/search/workbench.py`

## Changes
- `A` `src/cadrumo/application/search/workbench.py`
- `A` `src/cadrumo/application/search/tests/test_workbench.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p25-s368-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/search/tests/test_workbench.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/search/workbench.py src/cadrumo/application/search/tests/test_workbench.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/search/workbench.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/search/workbench.py` -> `pass`
