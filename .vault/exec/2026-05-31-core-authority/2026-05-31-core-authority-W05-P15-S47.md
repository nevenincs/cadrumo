---
step_id: S47
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W05.P15.S47 — SECURE_OBJECT key placement audit (RENAME-012)

## Audit result

`SECURE_OBJECT_CATALOGUE_KEY`, `SECURE_OBJECT_DEFAULT_KEY`, `SECURE_OBJECT_WORKFLOW_STATE_KEY` are consumed only within:
- `adapters/persistence/storage/_namespace_registry.py` (declarations and uses)
- `adapters/persistence/storage/__init__.py` (re-export only)
- `adapters/persistence/storage/test_namespace_registry.py` (tests)

Zero consumers in `domain/`, `application/`, or `entrypoints/`.

## Placement decision: stays in adapters/persistence/storage/_namespace_registry.py

These are storage-mechanism slugs — the literal `default_object_key` values for `SecureObjectNamespaceDefinition` records. Moving them to `domain/buckets/` or `application/workflow/` would invert the dependency: domain and application layers should not know about storage-layer object-key naming conventions. The constants encode persistence-layer implementation details, not domain or application concepts.

## Commit

`f76e5020f` — docs(storage): S47 SECURE_OBJECT key placement audit - stays in adapters/persistence/storage
