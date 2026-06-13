---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S450'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W19.P39.S450 - Refresh secure-storage guard inventories

Scope: refresh the secure-storage guard approval paths and production-write inventory
after concurrent test and application split-module moves.

## Description

- Added Wave `W19`, Phase `W19.P39`, and Step `W19.P39.S450` to track the guard repair
  explicitly.
- Updated hardening guard test path approvals from legacy flat test-module paths to the
  current `tests/` package layout.
- Preserved the explicit database-route approval guard; no assertion was weakened.
- Corrected the production file-write inventory root from the `src` directory back to
  the repository root.
- Updated reviewed writer inventory keys for moved ledger export and profile bundle
  CLI modules.
- Closed `W19.P39.S450` through `vaultspec-core vault plan step check`.

## Outcome

The secure-storage guard suite now executes against the current code layout and still
requires reviewed approval for explicit database-route setup and production file-write
sites.

## Validation

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/tests/test_hardening_convention_guards.py src/aeat/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/tests/test_hardening_convention_guards.py src/aeat/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

This is a guard-maintenance repair required by concurrent split-module work; it does
not add mocks, fakes, monkeypatches, skips, or xfails.
