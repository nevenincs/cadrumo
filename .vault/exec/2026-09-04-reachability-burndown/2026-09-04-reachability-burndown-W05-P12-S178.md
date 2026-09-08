---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:404a455d06b9b58d82e93062bd92ae6d3ae6eeb164e9c0e9a1b67a8e1c8cbe22'
step_id: 'S178'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the production-unreached committed custody data-file mutation facade and relocate the two deliberate corruption/crash mutations behind the existing test-support boundary, preserving capsule recognition and compare-and-swap detector strength without retaining a product API for manufacturing test states.

## Scope

- `profile custody capsule facade`
- `shared profile test support`
- `capsule lifecycle and label-ambiguity tests`
- `production-metastate gate`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `A` `src/cadrumo/adapters/persistence/storage/custody/tests/support.py`
- `M` `src/cadrumo/tests/profile_capsule.py`
- `M` `src/cadrumo/application/user_profile/tests/test_capsule_lifecycle.py`
- `verify:` `rg -n "replace_committed_profile_custody_data_file|replace_data_file|replace_test_profile_custody_data_file" src/cadrumo dev` -> `pass`
- `verify:` `uv run ruff check <S178 Python paths>` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_data_path_validation.py src/cadrumo/application/user_profile/tests/test_capsule_lifecycle.py src/cadrumo/entrypoints/cli/tests/test_active_profile_env_override_name.py src/cadrumo/entrypoints/cli/config/tests/test_profile_label_ambiguity_refusal.py` -> `pass` (19 passed)
- `verify:` `git diff --check -- <S178 paths>` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `fail` (two live findings)
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail` (354 exact symbols; 18 orphan test modules)

## Notes

The zero-target metastate gate improved from three findings to two. The exact unused signal improved from 355 to 354 while orphan tests remained at 18. Both remaining metastate findings are in the peer-dirty `filed_data_capture.py` and were deliberately left for separately grounded steps.
