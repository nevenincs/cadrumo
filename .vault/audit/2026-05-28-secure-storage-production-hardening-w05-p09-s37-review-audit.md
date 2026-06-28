---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
---



# `secure-storage-production-hardening` Code Review

No HIGH or CRITICAL findings were identified in the W05.P09.S37 review.

S37-001 | MEDIUM | CLI audit workflow still has an un-migrated settings construction path
`EvidenceBundleService` now persists through `secure_object_repository_for_bucket`, and the default no-argument service path is runtime-created. However, an existing CLI audit workflow test still seeds a bundle with `EvidenceBundleService(settings=Settings())` while the active profile/session is scoped through `override_settings`. That bare `Settings()` does not carry the scoped storage root, so the seed writes to a different bucket database than the CLI later reads. The focused modified suites pass, but `uv run pytest src/aeat/entrypoints/cli/test_audit_verbs.py -q` fails five audit verb roundtrips with `no evidence bundle matches ... in bucket 'operator'`. This leaves public audit verb coverage broken after the storage backend migration and shows that callers providing an unscoped `Settings` instance can silently split evidence-bundle writes from active-profile reads. The fix should migrate the seed/caller path to the same runtime-profile settings contract used by the new evidence tests, or stop passing bare `Settings()` where the active runtime settings are required.

## Review Notes

The previous bucket-local JSONL loader and saver were removed from `src/aeat/application/evidence/_service.py`. The new `EvidenceBundleRepository` uses the registered `application_evidence_bundles` namespace and the default service path calls the runtime repository factory before constructing the secure-bound repository.

The new namespace is exported through `src/aeat/adapters/persistence/storage/__init__.py`, registered in `src/aeat/adapters/persistence/storage/_namespace_registry.py`, covered by `src/aeat/adapters/persistence/storage/test_namespace_registry.py`, and listed in the hierarchy inventory.

No fakes, mocks, stubs, monkeypatch, skips, xfails, naked environment calls, or swallowed exceptions were found in the modified S37 files during the review scan.

## Verification

Passed: `uv run pytest src/aeat/application/evidence/test_evidence.py src/aeat/adapters/persistence/storage/test_namespace_registry.py -q`

Failed: `uv run pytest src/aeat/entrypoints/cli/test_audit_verbs.py -q` with five route-mismatch failures where CLI audit verbs cannot find the seeded evidence bundle.

## Resolution Update

S37-001 | RESOLVED | CLI audit workflow now uses the runtime-created default service path
The follow-up change removed the bare `Settings()` construction from `src/aeat/entrypoints/cli/test_audit_verbs.py` and now seeds bundles with `EvidenceBundleService().build(...)`. Re-checking the diff confirms `_seed_bundle()` no longer passes an unscoped settings instance, so the seed path and CLI audit verb path both resolve through the active runtime settings and repository factory.

Re-verified on 2026-05-28:

Passed: `uv run ruff check src/aeat/application/evidence src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`

Passed: `uv run pytest src/aeat/application/evidence/test_evidence.py src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_auth_session_cache_remote_namespaces_are_registered src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_namespace_registration_coverage_is_present src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_every_discovered_production_secure_object_namespace_is_registered -q` with 28 passed.
