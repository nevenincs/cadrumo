---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4ae747cfe041d54ef4e20c613bd005bf4003c659a6d606cf68bafcb2eca90617'
step_id: 'S365'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define immutable account-session, zone-availability, next-action, declaration-resume, Ledger-readiness, and agenda records for the Home projection

## Scope

- `src/cadrumo/application/overview/home_projection.py`

## Changes
- `M` `src/cadrumo/application/overview/home_projection.py`
- `M` `src/cadrumo/application/overview/tests/test_home_projection.py`
- `M` `.vault/audit/2026-09-02-tui-architecture-w08-p25-s365-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/overview/tests/test_home_projection.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/overview/home_projection.py src/cadrumo/application/overview/tests/test_home_projection.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/overview/home_projection.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/overview/home_projection.py` -> `pass`
