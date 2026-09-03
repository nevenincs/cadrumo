---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:05e59c62eea48d4f2bb92eaad6c0036f1132d76772bf4b30af964ad7bc2679dd'
step_id: 'S403'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Compose production account doors and root affordances for Profile, change user, password, language, appearance, sign out, expiry, and authenticated-session recomposition

## Scope

- `src/cadrumo/entrypoints/tui/account.py`
- `src/cadrumo/entrypoints/tui/app.py`
- `src/cadrumo/entrypoints/tui/launcher.py`
- `and focused account lifecycle tests`

## Changes

- `M` `src/cadrumo/entrypoints/tui/account.py`
- `M` `src/cadrumo/entrypoints/tui/app.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_app.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p28-s403-review-audit.md`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/entrypoints/tui/tests/test_account.py src/cadrumo/entrypoints/tui/tests/test_app.py src/cadrumo/entrypoints/tui/tests/test_bootstrap.py src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py` -> `pass`
