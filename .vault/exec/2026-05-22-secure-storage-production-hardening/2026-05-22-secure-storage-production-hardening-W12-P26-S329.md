---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S329'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S329 registry audit close

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Audited `domain.calculations.registry._schema` against the target `remote-mirror` (owner `W12.P24.S98`).
- Confirmed the module is the strict pydantic v2 schema for `ModeloDefinition` / `ModeloRevision` / `CasillaDefinition` / `FormulaDefinition` / `DataBindingDefinition` and related record types; pure record schema, no I/O.
- The `remote-provider` signal is appropriately accounted for by the schema's typed handling of remote-provider binding metadata (e.g., AEAT live-read snapshot id references on `DataBindingDefinition`), which the runtime resolves through captured-snapshot mirrors per the live-AEAT charter.

## Outcome

- AFR-227 closed: justified remote-mirror through schema typing of provider-binding metadata. No source change required.

## Notes

- Audit-only Step.
