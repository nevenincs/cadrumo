---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:413abf4e1c72136019c03973cfb67e59defc371fa382bdf662405ffad118959c'
step_id: 'S377'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build the Declarations landing, revision and filing-history routes around existing Modelo workspace destinations

## Scope

- `src/cadrumo/entrypoints/tui/declarations/`

## Changes
- `A` `src/cadrumo/entrypoints/tui/declarations/`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s377-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/declarations/tests src/cadrumo/application/modelo/tests/test_declarations_workspace.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/declarations` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/declarations` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/declarations` -> `pass`
