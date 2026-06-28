---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S41'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p10-s41-review-audit]]'
---



# `secure-storage-production-hardening` `W05.P10.S41`

Added remote ciphertext mirror policy fields to the secure-object namespace
registry.

- Modified: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P10-S41-review.md`

## Description

`SecureObjectNamespaceDefinition` now carries an explicit remote mirror policy
plus revision and integrity-manifest requirements. Production namespaces default
to ciphertext mirroring with revision and integrity metadata required, matching
the secure-storage architecture requirement that remote providers mirror opaque
ciphertext and registry-owned policy rather than plaintext application state.

The registry validator rejects inconsistent combinations: ciphertext mirror
namespaces cannot disable revision or integrity metadata, and local-only or
test-only namespaces cannot require remote mirror metadata. Test-only registry
namespaces are marked as `test_only` and excluded from remote mirror metadata
requirements.

The storage package publicly exports the new remote mirror policy enum.

## Tests

- `uv run ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run pytest src/aeat/adapters/persistence/storage/test_namespace_registry.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
- `git diff --check -- src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`

Review audit: `2026-05-28-secure-storage-production-hardening-W05-P10-S41-review`.
