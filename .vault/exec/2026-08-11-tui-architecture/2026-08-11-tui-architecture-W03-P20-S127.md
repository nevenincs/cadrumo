---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e81a67427009768944d8968ed167958bd87954450718826672af4eca62d0b214'
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
- Add real-authority fixed-point and adversarial selector, union, collection, duplicate, stale, and unclassified tests.

## Outcome

- The manifest is frozen, sorted, digested, and validates exactly against the current public registry schema fixed point.
- Raw registry authoring, loaders, and private registry modules remain outside the application boundary.
- Focused Ruff passed; focused basedpyright reported 0 errors and 0 warnings; the S127 integration module passed 5 tests.
- The feature-scoped Vault check passed with only external feature warnings. Post-change Vaultspec RAG found no indexed semantic duplicate, and exact census found one manifest owner module.

## Notes

- S127 remains open and review-ready; no plan status was changed.
- Shared-tree facade bridge correction was handled in a separate current-only commit and is outside S127 scope.
