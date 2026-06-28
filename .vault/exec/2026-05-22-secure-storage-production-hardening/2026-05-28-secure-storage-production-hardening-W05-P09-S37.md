---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S37'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s37-review-audit]]'
---

# `secure-storage-production-hardening` `W05.P09.S37`

Migrated evidence bundle persistence from bucket-local JSONL files to a runtime-created secure-object repository and registered the evidence-bundle namespace.

- Modified: `src/aeat/application/evidence/_service.py`
- Modified: `src/aeat/application/evidence/__init__.py`
- Modified: `src/aeat/application/evidence/test_evidence.py`
- Modified: `src/aeat/entrypoints/cli/test_audit_verbs.py`
- Modified: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Modified: `.vault/audit/2026-05-27-secure-storage-hierarchy-namespace-inventory.md`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P09-S37-review.md`

## Description

`EvidenceBundleService` no longer reads or writes `settings.aeat_audit_dir / "evidence-bundles" / {bucket_id}.jsonl`. It now saves and loads `EvidenceBundle` records through `EvidenceBundleRepository`, a `SecureBoundRepository` subclass backed by a runtime-created secure-object repository for the requested bucket.

The storage registry now defines and exports `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE` with namespace `aeat.application.evidence.bundles`, AUDIT sensitivity, schema version `1`, bucket-local scope, and `{bundle_id}` object-key grammar. Namespace tests and the hierarchy inventory were updated to keep the registry contract auditable.

The CLI audit verb tests now seed bundles with `EvidenceBundleService()` so the seed path and CLI read path share the same active runtime settings. This resolves the S37 review finding that bare `Settings()` split seeded writes from CLI reads.

## Tests

Validation performed:

- `uv run ruff check src/aeat/application/evidence src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run pytest src/aeat/application/evidence/test_evidence.py src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_auth_session_cache_remote_namespaces_are_registered src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_namespace_registration_coverage_is_present src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_every_discovered_production_secure_object_namespace_is_registered -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `git diff --check` on the S37 modified files and vault artifacts.

The focused Python test gate passed with 28 tests.
