---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:f9410b9f1b33ed72393a6cf1e04ea659b5f69ad58490227576c4d87589ceb4c3'
step_id: 'S19'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the namespace registry's filesystem-name constants as consumers of the core taxonomy while leaving the secure-object namespace definitions untouched, gated by a test asserting each constant equals its taxonomy member value

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`

## Description

- Rewrite the namespace registry's filesystem-name constants as consumers of the core taxonomy, leaving the secure-object namespace definitions untouched.

## Outcome

Landed in commit `8abb148218` ("make the namespace registry a consumer of the core taxonomy"). All 11 constants in `_namespace_registry.py` rewritten as `storage_location(StorageCategory.X).subpath` calls; the `SECURE_OBJECT_*` namespace keys confirmed untouched per ADR R10's explicit carve-out, and the import direction (`adapters` → `core`) is the legal one. Gated by new `test_namespace_registry_taxonomy_consumer.py`, an AST-walk asserting every constant equals its taxonomy member's subpath in both directions.

## Notes
