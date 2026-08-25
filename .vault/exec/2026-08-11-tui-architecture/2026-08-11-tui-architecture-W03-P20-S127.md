---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2251a919bc2ad39b7d9fa82725edf40c5be1513ed19c96e0dd3c1d7c62ed8b30'
step_id: 'S127'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Generate the exhaustive registry model-and-field classification manifest from validated public schema types, classifying every reachable leaf and discriminator branch exactly once as projected, canonically derived, or backend-only with destination, owner, and bounded reason

## Scope

- `src/cadrumo/application/modelo/_workspace_manifest.py`
- `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`

## Description

- Generate a deterministic public-schema field manifest from `RegistrySnapshot` and registered selector roots.
- Traverse resolved Pydantic models, unions, discriminators, mapping values, and collection elements with canonical paths.
- Delegate export-layout roots to `derive_export_layouts_from_bindings` and declare the S126 `FIELD_MANIFEST` producer contract.
- Restrict formula-operand projection to the canonical identity and literal union branches representable by the Workspace operand DTO; retain optional absence, operator grammar, and dispatch containers as bounded registry-owned declarations.
- Add live M303 adversarial assertions for identity, literal, optional, operator, and dispatch branches, alongside selector, union, collection, duplicate, stale, and unclassified checks.

## Outcome

- The manifest is frozen, sorted, digested, and validates exactly against the current public registry schema fixed point.
- Raw registry authoring, loaders, and private registry modules remain outside the application boundary.
- Focused Ruff and ty passed. The focused live M303 integration lane passed 6 tests in 71.05 seconds.
- Exact source census confirms one manifest owner module; the implementation consumes only the public calculation-registry facade and prior S125/S126 contracts.

## Notes

- S127 remains open pending independent review; no plan status was changed.
- No facade bridge or S128 assembly was introduced.
