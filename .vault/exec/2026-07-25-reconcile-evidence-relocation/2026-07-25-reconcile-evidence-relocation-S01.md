---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S01'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Register the MODELO_RECONCILIATION_RECORDS secure-object namespace at AUDIT sensitivity and PROFILE_LOCAL scope and STRUCTURED_CUSTODY disposition, enrolling its durability floor and version and empty upgrader registry at birth as compatibility-lifecycle-checkpoint requires

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`

## Description

- Declare the namespace at AUDIT sensitivity, PROFILE_LOCAL scope and STRUCTURED_CUSTODY disposition, immediately beside the IVA-wallet reconciliation-decision pair it enrols under.
- Pin the schema version to the shared from-birth constant rather than a local literal, so the registry-wide lineage gate governs it.
- Register it in the storage hierarchy registry and export it from the storage package facade.
- Record the key grammar and both of its load-bearing properties as a comment on the definition itself.
- Move the namespace-inventory count gate from sixty-six rows to sixty-seven.

## Outcome

The store enrols under an existing shape rather than inventing one: the same sensitivity, scope and disposition as the two shipped IVA-wallet reconciliation namespaces.

Floor, version and empty upgrader registry are enrolled at birth by construction rather than by a second declaration. Because the namespace sits at the from-birth schema version, its upgrade chain from the durability floor is complete with no upgraders registered, and the registry-driven schema-lineage gate binds it automatically from the moment it is registered. A later version bump cannot ship without landing its one-hop upgrader.

Every registry-driven gate was run and passes: schema lineage, persisted-format enrollment, namespace adoption, and repair-policy coverage.

## Notes

The only gate that needed a change was a hardcoded inventory count, whose test name embeds the number; the name and the assertion were moved together so the two cannot drift.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.
