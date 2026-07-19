---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S25'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Require yes for reset start and resume while keeping status non-destructive

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`

## Description

- `test_config_reset_start_refuses_without_yes`: `config reset start` (no `--yes`) refuses.
- `test_config_reset_status_is_read_only_and_needs_no_yes`: `config reset status` succeeds with no confirmation and mutates nothing.
- `test_config_reset_removed_scope_spelling_is_rejected`: the retired flat `config reset --scope auth --yes` has no alias or compatibility parser.
- `test_config_reset_resume_refuses_without_yes`: `config reset resume` (no `--yes`) refuses.

## Outcome

Verified against HEAD (`8af409cd3f`), not re-implemented; landed by commit `38eba09021`. Ran `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py -m integration -q --no-header`: 12 passed in 13.60s (includes the four reset-family assertions above plus the pre-existing ledger-reset and auth-reset yes-gates). The removed-scope-spelling test is direct evidence that S20's hard cut of the old flat `--scope` verb is proven, not just assumed absent.

## Notes

No incidents.
