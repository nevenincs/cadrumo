---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S87'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S86]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p21-s87-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P21.S87`

Added focused real-behavior tests proving migrated runtime repository defaults are bound to active profile storage and reject unsafe runtime states across the W12.P21 repository families.

## Changes

- Added a cross-family runtime migration suite covering workflow state/runs, bucket events, AEAT auth session storage, auth diagnostics, Google OAuth records, LLM cache/usage, attachments, transaction catalogues, invoices, filing drafts/amendments, submissions, justificantes, filing history, modelo catalogues, calculation observations, IVA compensation history, usage ratios, Borrador 100 snapshots, repair decisions, diagnostics inventory probes, profile assets, profile inventory, profile amortizacion, and Sede artefact/observation storage.
- Proved migrated defaults refuse an active profile without an active bucket session.
- Proved migrated defaults refuse route/session mismatch before returning absent-row fallbacks.
- Proved writes are isolated per active profile bucket by writing under one bucket, reading absence under another, writing different records in the second bucket, then rereading the original bucket with the same real ephemeral master key.
- Kept the suite free of storage monkeypatching, `AEAT_DATABASE_URL`, explicit database URLs, mocks, skips, xfails, `noqa`, pragmas, and type suppressions.

## Validation

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/domain/test_runtime_repository_enrollment.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/domain/test_runtime_repository_enrollment.py -q` - 97 passed.
- `rg -n "noqa|pragma: no cover|type: ignore|monkeypatch|AEAT_DATABASE_URL|Settings\\(aeat_database_url|_Fake|_Stub|patch\\(" src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` - no matches.

## Notes

- The new tests deliberately reuse a fixed ephemeral master key across bucket-switch contexts so the assertions isolate runtime routing behavior rather than accidental key rotation.
- Direct low-level route/refusal tests remain in `test_runtime.py`; the S87 suite now covers the migrated repository families that converge on the shared runtime repository boundary.
