---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8681d56fc68a692a2627337325472426e840e11ae8ed30b7112732c3978fe8a3'
step_id: 'S373'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Measure both candidates at supported terminal sizes, both themes, and every shipped locale for clipping, scroll ownership, focus reach, and task keystrokes

## Scope

- `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`

## Changes
- `M` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p26-s373-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
