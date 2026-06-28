---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S168'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S168` Secure-Bound Contract Runtime-Default Slice

Closed `AFR-066` by removing the shared envelope contract suite's direct secure-object constructor and isolating the contract harness from the operator's active-profile pointer.

## Changes

- Replaced the foreign-class fixture write in `_repository_test_suite.py` with the repository instance's existing object store.
- Removed the now-unused `SecureObjectRepository` import from the shared contract suite.
- Isolated the contract harness under a temporary `AEAT_LOCAL_STORAGE_ROOT` while it binds a temporary `AEAT_DATABASE_URL`, so local active-profile pointers cannot bleed into process-default contract checks.
- Updated the contract suite generics to the project-standard Python type-parameter syntax after this file entered the lint surface.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py -q` - 28 passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "submission or justificante or filing_drafts or filing_amendments" -q` - 8 passed, 69 deselected.
- `uv run ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py` - passed.
- Focused code review re-review reported no findings.

## Residual Debt

- The contract suite still uses `monkeypatch` because it predates the current stricter testing policy and is built around process-environment route rebinding. This slice removed the constructor bypass and pointer bleed without redesigning the entire historical contract harness.

## Tracking

Completed internal tasklist for this slice:

- Remove the contract suite's direct secure-object constructor: complete.
- Preserve foreign-class rejection coverage through the real repository object store: complete.
- Isolate process-default contract tests from local active-profile pointer state: complete.
- Verify tests, lint, constructor inventory, plan row closure, and review: complete.
