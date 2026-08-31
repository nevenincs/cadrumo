---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:169b6aff460e60394300eb7c6d0fb5e19251e32c5dc8f03266e5292042736b74'
step_id: 'S128'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in filesystem.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/filesystem.py`

## Changes

- `A` `src/cadrumo/adapters/persistence/storage/custody/_capsule_filesystem.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/filesystem.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/_inventory.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule_discovery.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S128.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/custody/filesystem.py src/cadrumo/adapters/persistence/storage/custody/_capsule_filesystem.py src/cadrumo/adapters/persistence/storage/custody/capsule.py src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py src/cadrumo/adapters/persistence/storage/custody/_inventory.py src/cadrumo/adapters/persistence/storage/custody/capsule_discovery.py src/cadrumo/adapters/persistence/storage/custody/capsule_records.py` -> `pass` (`All checks passed!`; exit 0)
- `verify:` `uv run --no-sync pytest --collect-only -q src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_ceilings_have_one_home.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_deletion_protocol.py src/cadrumo/adapters/persistence/storage/custody/tests/test_local_record_witness_contract.py src/cadrumo/adapters/persistence/storage/custody/tests/test_local_record_write_outlasts_a_reader.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_data_path_validation.py` -> `pass` (`63 tests collected in 0.20s`; exit 0)
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_ceilings_have_one_home.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_deletion_protocol.py src/cadrumo/adapters/persistence/storage/custody/tests/test_local_record_witness_contract.py src/cadrumo/adapters/persistence/storage/custody/tests/test_local_record_write_outlasts_a_reader.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_data_path_validation.py` -> `pass` (`63 passed in 15.55s`; exit 0)
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_relative_imports_resolve.py src/cadrumo/adapters/persistence/storage/custody/tests/test_nofollow_is_never_the_only_guard.py` -> `pass` (`5 passed in 19.12s`; exit 0)
- `verify:` `uv run --no-sync python -m dev.audit.size_budget` -> `fail` (`size budget: scanned 5607 modules, 15529 production callables; FAIL - 87 finding(s)`; exit 1; target absent)

## Notes

`uv run --no-sync ruff format --check src/cadrumo/adapters/persistence/storage/custody/filesystem.py src/cadrumo/adapters/persistence/storage/custody/_capsule_filesystem.py src/cadrumo/adapters/persistence/storage/custody/capsule.py src/cadrumo/adapters/persistence/storage/custody/_capsule_data.py src/cadrumo/adapters/persistence/storage/custody/_inventory.py src/cadrumo/adapters/persistence/storage/custody/capsule_discovery.py src/cadrumo/adapters/persistence/storage/custody/capsule_records.py` exits 1: `capsule_records.py` would be reformatted at lines 250 and 306. Those untouched pre-existing blank-line findings remain outside S128; scoped ruff check above passes.
