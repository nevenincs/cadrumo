---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S371'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S371` Usage Ratios Runtime-Default Slice

Closed `AFR-269` for the usage-ratio service by removing the service-level direct secure-object constructor and binding default persistence to the requested bucket's storage runtime.

## Changes

- Migrated `load_usage_ratios` and `save_usage_ratios` defaults from direct `SecureObjectRepository()` construction to `secure_object_repository_for_bucket(bucket_id)`.
- Preserved explicit `objects=` injection for callers that already own a repository, while preventing implicit writes into a mismatched active bucket database.
- Kept blank bucket validation on the domain `UsageRatioPersistenceError` surface before runtime lookup.
- Wrapped non-UTF-8 encrypted payload bytes as `UsageRatioPersistenceError` with error logging instead of leaking `UnicodeDecodeError`.
- Updated real-runtime tests so usage-ratio and census-guard fixtures activate the same bucket ids passed to the service.
- Closed the file-level plan row with `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S371` and marked `AFR-269` as migrated in the audit register.

## Validation

- `uv run pytest src/aeat/domain/usage_ratios -q` - 47 passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k usage_ratios src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k usage_ratios src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_application_repository_defaults_isolate_active_profile_writes -q` - 2 passed, 65 deselected.
- `uv run ruff check src/aeat/domain/usage_ratios/_service.py src/aeat/domain/usage_ratios/test_service.py src/aeat/domain/usage_ratios/test_census_refuse_load.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/domain/usage_ratios/_service.py` - no remaining direct constructor hits.
- Focused code review re-review reported no findings.

## Residual Debt

- The broader `W12.P21.S84` domain repository rollout still includes the remaining pending `AFR-*` rows for filing, invoice, justificante, modelo, submission, transaction, and related domain runtime defaults.

## Tracking

Completed internal tasklist for this slice:

- Select `AFR-269` as the next direct-constructor migration target: complete.
- Bind default usage-ratio persistence to the requested runtime bucket: complete.
- Preserve explicit repository injection: complete.
- Add route-mismatch and non-UTF-8 corruption regressions without mocks or fakes: complete.
- Repair census-guard test runtime enrollment exposed by route strictness: complete.
- Run focused tests, lint, constructor inventory, plan row closure, and code review: complete.
