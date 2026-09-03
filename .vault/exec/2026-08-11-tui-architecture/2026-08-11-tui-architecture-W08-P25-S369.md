---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:25b0d6813a38cb68171fa3b6bcdd971031d872ec49c63e84b43d30b9d6f4493a'
step_id: 'S369'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define the TUI destination catalogue, explicit admission states, screen-factory protocol, and semantic focus identities

## Scope

- `src/cadrumo/entrypoints/tui/navigation.py`

## Changes
- `A` `src/cadrumo/entrypoints/tui/navigation.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_navigation.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p25-s369-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/entrypoints/tui/tests/test_navigation.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/navigation.py src/cadrumo/entrypoints/tui/tests/test_navigation.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/navigation.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/navigation.py` -> `pass`
