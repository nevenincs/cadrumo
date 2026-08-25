---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fc2ed6afc8a3dca8f6228d2c61f062680f8b31d54714b7f98af806c91bc67ba3'
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
- Traverse resolved Pydantic models, unions, discriminators, mapping values, collection elements, and traversable type aliases with canonical paths.
- Delegate every non-null union arm through the canonical annotation walker after emitting its union coordinate once, preventing omission of nested mapping, collection, alias, and model leaves without duplicate terminal nodes.
- Delegate export-layout roots to `derive_export_layouts_from_bindings` and declare the S126 `FIELD_MANIFEST` producer contract.
- Restrict formula-operand projection to the canonical identity and literal union branches representable by the Workspace operand DTO; retain optional absence, operator grammar, and dispatch containers as bounded registry-owned declarations.
- Add live M303 assertions for formula identity, literal, optional, operator, dispatch, and nested dispatch-parameter branches, plus synthetic nested-union traversal coverage.

## Outcome

- The manifest is frozen, sorted, digested, and validates exactly against the current public registry schema fixed point.
- Raw registry authoring, loaders, and private registry modules remain outside the application boundary.
- Focused Ruff and ty passed. The focused live M303 integration lane passed 8 tests in 38.79 seconds.
- Exact source census confirms one manifest owner module; the implementation consumes only the public calculation-registry facade and prior S125/S126 contracts.
- Independent review approved the final traversal and projection remediation.

## Notes

- S127 is closed after independent approval.
- No facade bridge or S128 assembly was introduced.
