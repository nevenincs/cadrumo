---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S01'
related:
  - "[[2026-06-10-live-justificante-reconcile-plan]]"
---




# Register the live justificante-capture secure-object namespace at FINANCIAL sensitivity and re-export it, verified by the namespace registry test

## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py`

## Description

- Add `LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE` (FINANCIAL, bucket-local,
  object-key grammar `justificante-capture-snapshot:{bucket_id}:{snapshot_id}`)
  mirroring the borrador and expedientes live-snapshot namespaces.
- Enrol it in `STORAGE_NAMESPACE_REGISTRY.namespaces` and the module `__all__`.
- Re-export it from the storage package surface (import block and `__all__`).
- Add a focused registry test asserting the registered contract (key, namespace,
  sensitivity, object-key grammar, scope).

## Outcome

Namespace registry test suite green (34 passed). Storage package collects clean
(841 tests). Landed as one atomic explicit-path commit `7267be79f`.

## Notes

The production-namespace AST coverage gate
(`test_every_discovered_production_secure_object_namespace_is_registered`)
couples this Step to `S02`: the namespace must exist before `_justificante.py`
references it, so registration ships first. No incidents; no scaffolds left.
