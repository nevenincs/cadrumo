---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S50'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W07.P12.S50`

## Description

- Inventory remaining classified secure-SQL hygiene files from the current static guard and raw AST constructor scan.
- Cross-check raw default SQL-backed repository hits against package-level runtime fixtures and the accepted `aeat.tests.secure_sql` helpers.
- Produce a slice map for the next application, CLI, and domain hygiene rows without repairing code in this inventory step.

## Outcome

Closed.

The current secure-SQL hygiene guard is green:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` -> 2 passed.

Inventory findings:

- Guard-enforced red backlog: none. The guard found no tests combining `EphemeralMasterKeyProvider` with default SQL-backed repository writes outside sanctioned temporary database/runtime isolation, and no database-storage tests using literal secret passphrases.
- Raw AST scan still finds 75 test files and 408 default SQL-backed constructor calls. This is not itself a failure: many files intentionally exercise runtime defaults and are isolated by `isolated_runtime_profile`, package autouse fixtures, or explicit secure-SQL helper imports.
- Package-level isolation matters. `src/aeat/application/filing/conftest.py` provides autouse `isolated_runtime_profile(..., bucket_id="filing-test")`, so the raw hits in `test_repository.py`, `test_history_repository.py`, and `test_complementaria_repository.py` are already covered by a real active-profile runtime even though the constructor calls are defaulted.
- Application calculation and live tests with `CalculationObservationRepository`, `IvaCompensationHistoryRepository`, and `IvaWalletDecisionRepository` are mostly wrapped by `isolated_runtime_profile`; they should remain runtime-default tests unless a specific file lacks the helper.
- Domain repository roundtrip tests for attachments, invoices, justificantes, submissions, and bucket events are already in the runtime-helper bucket and should be treated as isolated unless a future guard reports a concrete violation.

Slice map for follow-up rows:

- W07.P12.S51 application/CLI candidate: focus on files where the raw scan reports default constructors but only `secure_sql` import or plain `override_settings`, not an explicit runtime fixture in the same file. Initial candidates are `src/aeat/application/modelo/test_export.py`, `src/aeat/application/modelo/test_reconcile.py`, `src/aeat/application/user_profile/test_profile_repository.py`, and CLI files under `src/aeat/entrypoints/cli` that default `BucketEventHistoryRepository`, `WorkUnitCatalogueRepository`, `CalculationRevisionCatalogueRepository`, or `IvaWalletDecisionRepository`.
- W07.P12.S52 validation candidate: extend or document the guard so it can recognise package-level autouse `isolated_runtime_profile` fixtures. This avoids misclassifying already-isolated package tests while preserving the current real-behavior prohibition on fakes, stubs, monkeypatch, skips, and xfails.
- W07.P12.S53 domain candidate: keep `src/aeat/domain/{attachments,buckets,invoices,justificante,submission}` as already isolated through runtime-helper tests; only select a repair slice if a focused file proves it lacks the helper or writes through a process-default database route.

## Notes

No HIGH or CRITICAL issue was identified in this inventory step. The remaining work is classification/refinement, not a currently failing guard.
