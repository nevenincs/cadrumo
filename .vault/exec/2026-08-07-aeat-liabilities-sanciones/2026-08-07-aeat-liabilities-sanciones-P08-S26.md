---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6d0a962fbd1287ddc368c7d03ee7d54c2be07924c1e58c2224a0ad857dc87a5b'
step_id: 'S26'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Add NotificationDocumentService storing the fetched bytes through the encrypted content-addressed AttachmentStore resolved the way application/ledger/_actions_common.py resolves it, delegating to that single-writer primitive rather than re-implementing its write path, verified by a unit test asserting the store receives the bytes and the service opens no second write path

## Scope

- `src/cadrumo/application/live/_notification_documents.py`

## Description

- Delete the second copy of the attachment-store default-construction idiom from the live
  notification custody service and the ledger action services.
- Give the resolver one canonical home in the package that owns the class, export it from
  that package's facade, and sweep all three call sites in one commit.
- Move the deferred cross-layer edge inventory with the code, so no declared row describes
  an edge that no longer exists.
- Cover the resolver's own contract in the owning package's suite, and cover the service's
  delegation through the injection point the service already declares.

## Outcome

The service was already delegating its byte write to the shared ingestion primitive and
opened no second write path, so that part needed no change and is now locked by tests. The
real finding was a duplication: the fallback that turns an optional injected port into a
concrete store existed in two application packages, neither of which owns the class, and the
ledger copy's own docstring claimed to be the single home.

The resolver now lives once, beside the class it constructs. The ledger call sites keep
their deferred import so the runtime cross-layer graph is unchanged; the live service folds
the resolver into the storage import it already had, adding no new module-pair edge.

Modified files:

- `src/cadrumo/adapters/persistence/storage/attachment.py`
- `src/cadrumo/adapters/persistence/storage/__init__.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_attachment_store_roundtrip.py`
- `src/cadrumo/application/ledger/_actions_common.py`
- `src/cadrumo/application/ledger/_actions_manual.py`
- `src/cadrumo/application/live/_notification_documents.py`
- `src/cadrumo/tests/test_deferred_cross_layer_imports.py`

Delegation is asserted at the port rather than at the database: the injected store is a real
encrypted store with its calls recorded, so what the test reads is what genuinely crossed
the boundary. A store whose byte write refuses proves no second route exists, and the
manifest's full provenance proves the write went through the shared primitive rather than a
convincing hand-rolled imitation. The store's file-path entry point refuses outright,
because nothing on this path may hand custody a filesystem path.

## Notes

Consumers were confirmed by search to be exactly the two ledger sites and the live service
before the sweep began; the sweep did not widen. The gate baseline and the owning package's
facade moved in the same commit, which is the relocation contract rather than an extension
of it.
