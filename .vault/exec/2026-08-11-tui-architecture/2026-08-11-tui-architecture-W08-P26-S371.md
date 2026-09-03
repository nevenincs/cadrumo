---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:ddc4da5a61af9499137b753ae8515d715c56cda14e48d2fdc7d02d6f2c949553'
step_id: 'S371'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build synthetic non-sensitive Home projections covering ready, locked, stale, never-captured, unavailable, empty, and blocked states

## Scope

- `src/cadrumo/entrypoints/tui/devtools/home_fixtures.py`

## Changes
- `A` `src/cadrumo/entrypoints/tui/devtools/home_fixtures.py`
- `A` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p26-s371-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/devtools/home_fixtures.py src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/devtools/home_fixtures.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/devtools/home_fixtures.py` -> `pass`
