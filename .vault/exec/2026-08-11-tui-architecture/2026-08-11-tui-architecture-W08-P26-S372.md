---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:cb98fd5751e7b4448b91f3f485880ecf9ec2e92d709e1b3f7090c57fdf7c24a8'
step_id: 'S372'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement due-driven and task-launcher prototype screens over the same immutable projection

## Scope

- `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`

## Changes
- `A` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `A` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p26-s372-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
