---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:5cb121b346b79b7f6cb70130e639f60e477424539f8ae354601a070dec62a30b'
step_id: 'S377'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

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
