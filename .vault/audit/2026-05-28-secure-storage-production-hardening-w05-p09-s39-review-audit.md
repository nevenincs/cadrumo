---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-review-audit]]'
---



# `secure-storage-production-hardening` Code Review

Review target: `W05.P09.S39` live snapshot persistence migration.

Review result: no HIGH or CRITICAL issues found.

Validation run: `uv run pytest src/aeat/application/live/test_verify.py src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/application/test_storage_paths.py -q` passed, 93 tests.

S39-001 | MEDIUM | Live list paths silently drop decrypted rows whose payload bucket does not match the repository bucket
 `SecureSnapshotRepository.list_snapshots` in `src/aeat/application/live/_snapshot_base.py:430` decrypts every record in the registered namespace, then filters rows with `if _bucket_id_of(snapshot) == self._bucket_id` at `src/aeat/application/live/_snapshot_base.py:439`. `VerifyObservationRepository.list_observations` applies the same silent filter at `src/aeat/application/live/_verify.py:143`. Normal save paths prevent mismatched payloads, and load-by-id raises on a mismatch, so this is not a current routing bypass. The residual risk is that a corrupted or misrouted encrypted row in the active bucket database becomes invisible to list/latest views instead of failing closed as semantic bucket contamination. Follow-up should make list operations reject payload bucket mismatches, or record an explicit typed degradation, and add real secure-object corruption/misroute coverage without mocks or monkeypatches.

S39-002 | LOW | Stale implementation comments still describe file storage and stubbed snapshot testing after the secure-object migration
 The migrated live services route persistence through registered secure-object namespaces, but comments still say the public file-storage layout is preserved in `src/aeat/application/live/_expedientes.py:20` and `src/aeat/application/live/_notifications.py:30`. The live notification capture docstring also names the old `aeat.application.live.notifications` namespace at `src/aeat/application/live/__init__.py:1263` rather than the registered `aeat.application.live.notifications_snapshot` namespace, and says the function can be tested against a stubbed snapshot at `src/aeat/application/live/__init__.py:1267`. This does not change runtime behavior, but it conflicts with the S39 migration story and the no-stub test discipline. Follow-up should update those comments to describe encrypted secure-object storage and real-behavior test seams.

PASS-S39-001 | PASS | S39 live stores now route through runtime-created secure-object repositories
 `VerifyService`, `ExpedientesService`, and `NotificationsService` construct repositories through `secure_object_repository_for_bucket`; that helper calls `inspect_bucket_storage_runtime(...).secure_object_repository()`, preserving route readiness, active bucket database semantics, session freshness, and unsecured-backend refusal.

PASS-S39-002 | PASS | No live plaintext JSONL side store remains in the scoped live snapshot implementation
 The previous `settings.aeat_audit_dir / "live" / ... / {bucket_id}.jsonl` writers are gone from `src/aeat/application/live/_verify.py`, `src/aeat/application/live/_expedientes.py`, `src/aeat/application/live/_notifications.py`, and `src/aeat/application/live/_snapshot_base.py`. The sensitive persistence policy allowlist also removed the prior live `_verify.py` and `_snapshot_base.py` plaintext write exceptions.

PASS-S39-003 | PASS | Namespace registry is the authority for S39 identities, sensitivity, schema, and object-key grammar
 The S39 namespaces are registered as `live_expedientes_snapshot`, `live_notifications_snapshot`, and `live_verify_observations` with bucket-local scope, version 1 schema policy, and FINANCIAL or IDENTITY sensitivity. The application code imports those registry definitions instead of duplicating namespace string literals.

PASS-S39-004 | PASS | Tests use real runtime storage paths and do not rely on fakes, mocks, monkeypatches, skip, or xfail
 The focused live tests use `isolated_runtime_profile` and `isolated_profile_storage_root` helpers to create real active bucket storage, then assert secure-object rows exist and former plaintext JSONL paths do not. Static scans of the scoped test files found no `monkeypatch`, mocks, stubs, skips, xfails, naked `AEAT_` environment mutation, or ad hoc `Settings(aeat_database_url=...)` setup.
