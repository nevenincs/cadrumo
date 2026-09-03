---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:a76b0ef45bb564f634964a1d76b7a2a283d4a3177bf9a69c6b032cee57d2605c'
step_id: 'S385'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Add complete localized workbench, account, Ledger, Declarations, calendar, AEAT Sync, search, availability, and refusal messages through the canonical locale workflow

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/entrypoints/tui/home.py`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `uv run --no-sync python -m dev.locales set-batch <manifest>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py` -> `pass`
