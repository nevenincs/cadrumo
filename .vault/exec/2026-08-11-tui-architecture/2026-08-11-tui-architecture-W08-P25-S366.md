---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5f0c334464e362cccc119b33085398ca1c108194e56a2c5a92db55eea5bf0b73'
step_id: 'S366'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Compose HomeProjectionV1 from canonical profile, overview, Ledger, declaration, notification, and filing-evidence readers with no implicit network activity

## Scope

- `src/cadrumo/application/overview/home.py`

## Changes
- `M` `src/cadrumo/application/overview/home.py`
- `M` `src/cadrumo/application/overview/tests/test_home.py`
- `A` `src/cadrumo/application/overview/tests/test_home_projection.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p25-s366-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/application/overview/tests/test_home.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/overview/home.py src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/application/overview/tests/test_home.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/overview/home.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/overview/home.py` -> `pass`
