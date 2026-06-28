---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S252
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
---

# cross-domain-continuity W09.P41.S252 — Category A batch 1 migration (4/5 files clean)

## Outcome

Migrated 4 of 5 Category A test files to the secure fixture pattern established
by S208. The fifth file (`test_profile_incn_new_entity_paths.py`) has 3 tests
that resist drop-in migration and are flagged for S253.

### Files migrated cleanly

| File | Fixture used | Result |
|------|-------------|--------|
| `test_fast_path_no_state.py` | `isolated_sessionless_storage_root` | 4/4 PASS |
| `test_repair_bootstrap_exempt.py` | `isolated_sessionless_storage_root` | 12/12 PASS |
| `test_profile_create_taxpayer_type_paths.py` | `isolated_profile_storage_root` | 8/8 PASS |
| `test_profile_incn_new_entity_paths.py` | `isolated_profile_storage_root` | 11/14 PASS |

### Partial migration — `test_profile_incn_new_entity_paths.py`

3 tests call `_load_active_taxpayer_profile()` directly after a CLI invocation:

- `test_new_entity_first_two_profit_periods_flag_stores_the_bool`
- `test_profile_creates_without_new_entity_flag_leaves_fact_undeclared`
- `test_no_new_entity_first_two_profit_periods_flag_records_declared_false`

`_load_active_taxpayer_profile()` calls `workflow_state_repository().load()` which
requires an active `BucketSession`. The CLI invocation creates and tears down its
own session internally — no session survives after the runner returns. These tests
need an `isolated_runtime_profile` wrapper (S253) rather than the sessionless or
profile-only fixtures.

The 11 remaining tests in the file pass cleanly. The `AEAT_SECRET_STORE_BACKEND=unsecured`
and `AEAT_ALLOW_UNENCRYPTED` monkeypatches have been removed from the autouse fixture.

## Commits

- `17551ca28` — W09.P41.S252: migrate Category A tests to secure fixtures (batch 1)

## Files changed

- `src/aeat/entrypoints/cli/test_fast_path_no_state.py`
- `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`
- `src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py`
- `src/aeat/entrypoints/cli/test_profile_incn_new_entity_paths.py`

## Blocker for S253

The 3 failing tests in `test_profile_incn_new_entity_paths.py` need an
`isolated_runtime_profile` wrapper that keeps the `BucketSession` alive across
the direct `_load_active_taxpayer_profile()` call. S253 should either wrap those
3 tests in a real runtime profile fixture, or restructure them to assert via the
CLI `config profile show` surface (which does not require a live session).
