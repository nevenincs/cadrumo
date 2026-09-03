---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:47ffa7d508bf9862db6e88ea1499420875f7d13c2f474b8a6451e7016953af03'
step_id: 'S379'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build AEAT Sync overview, profile-census, filed-declaration, notification, evidence-comparison, and reconciliation screens with explicit pull and supported push actions

## Scope

- `src/cadrumo/entrypoints/tui/aeat_sync/`

## Changes

- `A` `src/cadrumo/entrypoints/tui/aeat_sync/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/aeat_sync/models.py`
- `A` `src/cadrumo/entrypoints/tui/aeat_sync/controller.py`
- `A` `src/cadrumo/entrypoints/tui/aeat_sync/routes.py`
- `A` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `A` `src/cadrumo/entrypoints/tui/aeat_sync/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/aeat_sync/tests` -> `pass`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/entrypoints/tui/aeat_sync && uv run --no-sync ruff check src/cadrumo/entrypoints/tui/aeat_sync && uv run --no-sync ty check src/cadrumo/entrypoints/tui/aeat_sync && uv run --no-sync basedpyright src/cadrumo/entrypoints/tui/aeat_sync` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/entrypoints/tui/aeat_sync --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`

