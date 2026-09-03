---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:428ea21fc937a7d442e3be09763984605c3bac76c344d024e827a79116178c00'
step_id: 'S375'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build the Ledger overview, entries, review, import, classification, evidence, and reconciliation screens over canonical application doors

## Scope

- `src/cadrumo/entrypoints/tui/ledger/`

## Changes
- `A` `src/cadrumo/entrypoints/tui/ledger/`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-slice1-review-audit.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-slice2-review-audit.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-slice3-review-audit.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-final-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/ledger/tests` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/ledger src/cadrumo/application/ledger/workspace.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/ledger` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/ledger` -> `pass`
