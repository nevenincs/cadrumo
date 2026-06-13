---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S453'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P41.S453 - Narrow secure-storage guard inventories

Scope: retire stale direct-environment allowances from the secure-storage guard
inventory and preserve only justified test surfaces.

## Description

- Removed the stale `PASSPHRASE_ENV_VAR` allowance for master-key tests after S452
  moved passphrase coverage to centralized `Settings` overrides and real prompt
  failure behavior.
- Added the custody lifecycle integration test to the guarded hardening-test surface
  so shortcut markers, fake/stub classes, skip/xfail markers, and environment
  mutations are scanned there too.
- Verified the remaining custody harness `os.environ.items()` use is limited to
  subprocess environment sanitization and is not a passphrase handoff.

## Outcome

The secure-storage hardening guard no longer carries a dead passphrase-env exception.
The remaining custody lifecycle env reference is covered by the guarded surface and
documented as non-secret harness isolation.

Validation:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/tests/test_hardening_convention_guards.py -q`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/tests/test_hardening_convention_guards.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

The explicit-route allowlist remains intentionally file-scoped for low-level SQL,
runtime route-classification, refusal-contract, and Settings/test-helper surfaces.
This step narrowed the stale direct-environment allowance without broadening the
explicit-route inventory.
