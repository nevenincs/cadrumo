---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d781e234c3f78fce8a3090b63b938b5d78e5b59163efcd58c8289218b100bc5f'
step_id: 'S38'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enroll inventory selector validation in registry binding construction

## Scope

- `src/cadrumo/domain/calculations/registry/_bindings.py`

## Description

- Import the canonical S37 inventory selector and validator into the registry binding aggregator.
- Enroll `BindingSourceKind.INVENTORY` atomically in the selector-model and validator dispatch registries.
- Export `InventorySelector` through the registry facade for later application consumers without exposing a private family module.
- Extend the exhaustive family build matrix with a valid inventory projection and a rival-casilla mutation.
- Prove binding construction hydrates the typed selector with exact activity identity and rejects operation-to-destination drift.
- Preserve the production inventory deferral for the later resolver-enrollment step.

## Outcome

Inventory is now a legal, strictly typed registry binding source at construction time and at the registry-build validation gate. Both canonical dispatch tables point to the single S37 selector contract; no selector or tax operation vocabulary was duplicated in the aggregator.

The public facade exposes the selector type needed by later cross-package source resolution while retaining the family module as its canonical definition. Production source disposition remains deferred: this step adds no resolver, registry binding, source readiness, or connected claim.

Focused verification passed: 93 registry construction, selector, build-validation, source-taxonomy, and source-disposition tests; scoped Ruff; scoped `ty`; and diff hygiene. Mandatory formal review reported zero critical, high, medium, or low findings after the S37 activity-identity remediation landed.

## Notes

The facade export is eager, consistent with the existing registry binding surface. The package's lazy export mechanism remains reserved for the oracle/browser tail. No unrelated shared-worktree changes were staged or modified.
