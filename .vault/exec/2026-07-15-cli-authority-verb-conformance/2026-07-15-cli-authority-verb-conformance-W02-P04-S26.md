---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:632a124a8bb78d1c35c3afe4e465d5cb301517abb005d361dfabaa1215df54b9'
step_id: 'S26'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Introduce one neutral reentrant active-profile pointer transaction service, retire the duplicate storage-adapter lock export, and route orchestration write, clear, capture, rollback, registration, and selection through the core-owned authority under a continuous whole-create-span lock with bounded fail-closed contention

## Scope

- `src/cadrumo/application/user_profile/_profile_pointer_transaction.py`
- `src/cadrumo/application/user_profile/_orchestration.py`
- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/adapters/persistence/storage/__init__.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_substrate_smoke.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_rotation.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`
- `dev/import_hygiene_test_debt.json`
- `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`

## Description

- Promote the existing exclusive file-lock authority through the public core facade, remove the duplicate storage-adapter export, and migrate its substrate and rotation test consumers.
- Add a neutral active-profile pointer transaction that reuses one transaction object for same-root nesting and rejects cross-root, cross-thread, inherited-process, and escaped use.
- Hold the pointer transaction across profile creation, provisional pointer publication, downstream setup, and exact-byte rollback.
- Route registration, selection, deletion, logout, and active-profile removal through the transaction boundary.
- Remove the former orchestration pointer wrappers, their three import-debt entries, and the stale sensitive-write exemption.
- Verify the focused behavior, import hygiene, dependency boundaries, formatting, and post-edit duplicate-authority searches.

## Outcome

- Same-root nested callers share one transaction object, while invalid ownership transitions fail closed before pointer access.
- Failed creation restores the exact prior pointer bytes while the lock remains held; simultaneous creation and rollback failures are retained in a `BaseExceptionGroup`.
- The focused serial suite passed with 57 tests and 41 deselections; the standalone import-hygiene lane passed 11 tests; the rollback lane passed 5 tests after the final exception-path hardening.
- Import-linter analyzed 3,419 files and 16,143 dependencies with all five contracts kept and none broken.
- Ruff, JSON parsing, compilation, exact-symbol scans, and post-edit Vaultspec-RAG grounding passed; the retired orchestration wrapper names and storage-adapter lock export are absent from their former declaration and consumer surfaces.
- Repository-level pointer serialization and profile-health ownership remain explicitly deferred to S27 and S28.

## Notes

- The first import-hygiene run exposed the storage-adapter lock facade as a second public declaration. Work stopped until the approved plan amendment was committed as `879ebd6ca7`, then the duplicate export was retired within S26.
- The inline real-behavior diagnostic first encountered a retired default-workspace product state, then a Windows log-handle cleanup issue; the final environment-isolated run passed. These were diagnostic-environment incidents, not product failures.
- An unrelated pre-existing comment change in the user-profile facade is peer-owned and is not part of this step.
- No data loss occurred, no scaffolds were left in runtime code, and no S27 or S28 source was changed.
