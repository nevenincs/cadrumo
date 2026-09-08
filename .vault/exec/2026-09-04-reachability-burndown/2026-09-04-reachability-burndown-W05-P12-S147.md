---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5f2f2a2112ab0f975bd79783460250f71dc671a1a32f473a4de2eb881de00436'
step_id: 'S147'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove development-state language from the purchase-evidence replacement refusal, stating the live immutability contract and recovery action directly in application code and every locale instead of telling operators detachment is unimplemented

## Scope

- `ledger evidence attachment refusal and localized operator messages`

## Changes

- `M` `src/cadrumo/application/ledger/actions_manual.py`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/ledger/tests/test_actions_update_evidence.py` -> `pass (8 passed)`
- `verify:` `uv run ruff check src/cadrumo/application/ledger/actions_manual.py` -> `pass`
- `verify:` exact four-locale and application-code development-state wording scan -> `pass (zero matches)`
