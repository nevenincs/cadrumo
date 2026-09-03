---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:0f9f1a3c49f4b373baa42faec2a5a926ecfb6cb1665a3b1371df9af515a55391'
step_id: 'S380'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Compose production Profile, change-user, password, appearance, language, and sign-out factories without duplicating their existing screens

## Scope

- `src/cadrumo/entrypoints/tui/account.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/account.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_account.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-account-factories-audit.md`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run pytest src/cadrumo/entrypoints/tui/tests/test_account.py src/cadrumo/entrypoints/tui/tests/test_navigation.py src/cadrumo/entrypoints/tui/tests/test_app.py -q` -> `pass`
