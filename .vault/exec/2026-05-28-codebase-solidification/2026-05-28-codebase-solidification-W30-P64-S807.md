---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S807'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Add session-scoped source_tree_ast fixture and migrate the ratchets to consume it

## Scope

- `src/aeat/tests/test_any_param_rationale_inventory.py`
- `src/aeat/tests/test_cast_rationale_inventory.py`
- `src/aeat/tests/test_core_time_deletion_and_cast_rationale.py`
- `src/aeat/tests/test_locale_tr_positional_inventory.py`
- `src/aeat/tests/test_parsing_enrollment_inventory.py`
- `src/aeat/tests/test_utc_validator_enrollment_inventory.py`

## Description

- Ground against HEAD: the session-scoped `source_tree_ast` fixture already
  exists in `src/aeat/conftest.py` (it memoises each `src/aeat/` `.py` file's
  AST once per session), and the shared inventory helpers already accept an
  optional cache argument, but the ratchet test functions still called those
  helpers with no argument and so re-parsed via the module-level `functools`
  cache instead of the session fixture.
- Confirm the plan-named closure ratchet family (`test_w17_p49_closure.py` and
  siblings) no longer exists; those PM-metadata-named files were removed in a
  later source-hygiene cleanup, so that part of the step is moot.
- Thread the `source_tree_ast` fixture into the six production-source AST
  ratchet test functions and forward it to their `production_ast_items` /
  `cast_rationale_violations` helpers.
- Add the `collections.abc.Mapping` import to the utc-validator ratchet so its
  test can carry the fixture annotation.

## Outcome

- Nine ratchet tests across the six files pass with the fixture wired.
- Behaviour proven equivalent: for the production surface the cache path and
  the original no-cache path scan the identical 1203-file set and produce
  identical violation lists, so the migration is a pure no-op on assertion
  logic.
- A mutation probe fed a crafted cache entry containing an unmarked `cast()`
  in a synthetic production module; the cast ratchet flagged it through the
  cache path, confirming the assertion still bites and is not weakened.
- Ruff clean.

## Notes

- `test_cross_module_imports_resolve.py` was deliberately left unmigrated: its
  collector uses `package_ast_items(cache, include_data=True)`, but the session
  cache is built from `package_python_files()` which excludes the `_data` tree,
  so threading the cache silently narrowed the scan and broke the
  import-baseline gate. Reverted to HEAD.
- `test_mock_inventory.py` and `test_monkeypatch_inventory.py` were left
  unmigrated: they scan test-control modules where the session cache offers
  negligible benefit over the existing per-path `functools` cache, and both are
  currently red from unrelated peer WIP under `dev/registry/newmodelo/tests/`
  (monkeypatch usage), so a green migration could not be verified. Confirmed
  those two tests already fail on HEAD, so the red is not owned by this step.
