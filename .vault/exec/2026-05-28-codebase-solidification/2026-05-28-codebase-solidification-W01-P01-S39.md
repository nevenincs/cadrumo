---
step_id: S39
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S39 — NamespaceRegistryError introduction

## Outcome

Added `NamespaceRegistryError(StorageError, ValueError)` to
`src/aeat/adapters/persistence/storage/errors.py`. Replaced all 13 bare
`raise ValueError(...)` guards in `_namespace_registry.py` — covering
`SecureObjectNamespaceDefinition._key_is_registry_safe` (2 raises),
`_namespace_is_sql_safe` (2), `_default_key_is_repository_safe` (2),
`StoragePathDefinition._key_is_registry_safe` (2),
`_segment_is_single_path_component` (2), and
`StorageHierarchyRegistry._reject_duplicate_keys_and_namespaces` (3).
Registered `INTEGRITY_STORAGE_NAMESPACE_REGISTRY` (`ErrorCategory.INTEGRITY`) in
`src/aeat/core/errors/registry/_adapters.py`. Added
`integrity_storage_namespace_registry` locale messages in en, es, ca, and hu.

## Files touched

- `src/aeat/adapters/persistence/storage/errors.py`
- `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- `src/aeat/core/errors/registry/_adapters.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

No bare `ValueError` raises remain in the validator/model_validator hooks of
`_namespace_registry.py`. `NamespaceRegistryError` inherits from `ValueError`
so Pydantic wraps field-validator raises in `ValidationError` as before.
