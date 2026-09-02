---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:334bef39f65b770cfa20fb925c2a224e8345e7dbf605dd203ed7ff75e504fe2c'
step_id: 'S366'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
