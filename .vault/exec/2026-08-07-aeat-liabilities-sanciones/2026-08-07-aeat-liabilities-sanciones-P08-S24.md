---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:72ba3e6126ae4ae6bde3d5cbb2a0d9d0767e14921ba6cc22d28a7dd659a8fd1d'
step_id: 'S24'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Add the LIVE_NOTIFICATION_DOCUMENT_NAMESPACE bucket-scoped namespace constant for the document manifest beside LIVE_DEUDAS_SNAPSHOT_NAMESPACE, verified by the existing namespace-uniqueness gate over the storage namespace constants

## Scope

- `src/cadrumo/adapters/persistence/storage`

## Description

- Declare the bucket-scoped namespace constant for the notification-document manifest beside the deudas and notifications snapshot namespaces.
- Carry it in the storage namespace registry tuple and the module export list.
- Re-export it from the storage package facade.

## Outcome

Delivered. The constant is bucket-scoped with full-custody-only disposition and financial sensitivity, and is reachable through the storage package facade rather than a private module path.

The row asked for verification by "the existing namespace-uniqueness gate over the storage namespace constants". What actually enforces uniqueness is stronger than a test: a model validator on the registry runs at import time over the real namespace tuple, so a duplicate key or namespace cannot be constructed at all. The registry's own test module proves that validator against synthetic registries and separately iterates the shipped collection on five other properties, including an AST discovery pass asserting every namespace found in the tree is registered. Coverage is by construction, not by enumeration, so no hardcoded namespace list exists to go stale.

## Notes

Recorded retrospectively. The constant landed with the custody service commit ahead of this campaign's reopening, so this record documents delivered state rather than fresh work. No code changed to close the row.
