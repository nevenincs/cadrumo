---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` audit: `exception hierarchy`

## Scope

Audited secure-storage exception classes for derivation from the central AEAT exception hierarchy and registry binding.

## Findings

- Pass: every imported secure-storage exception subclass of `AeatError` has a registered error code.
- Pass: `SecureStorageError` now derives from `AeatError` and binds to `FAIL_SECURE_STORAGE`.
- Pass: `StorageError`, `PersistenceError`, `RepositoryError`, bucket lifecycle errors, master-key errors, blob errors, crypto errors, retention errors, and validation errors derive through AEAT base classes rather than bare `Exception`.
- Pass: `StorageValidationError` and `PathContainmentError` retain `ValueError` compatibility while also deriving from AEAT storage bases.
- Review: the only direct `Exception` class found under the storage tree is a test-local helper in `src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py`; it is not a production exception type.

## Remaining Work

No base-class remediation is required from this audit. `W11.P18.S72` remains open because S65 identified constructor/message behavior that can still bypass registry-backed locale rendering even when the exception hierarchy itself is valid.

## Validation

`uv run pytest src/aeat/core/errors/test_registry_enforcement.py -q` reported 4 passed.

The audit also enumerated secure-storage `AeatError` subclasses and confirmed each has a bound registry code.
