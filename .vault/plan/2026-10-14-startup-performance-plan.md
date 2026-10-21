---
tags:
  - '#plan'
  - '#startup-performance'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-10-13-startup-performance-operation-contract-manifest-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:eda996490fce4db34f95951ce22b90b73228cbd2deac43306f5ada9408164b5c'
---

# `startup-performance` plan

Finish the generated operation contract manifest so contract readers stop composing every operation.

## Description

Approved 2026-10-14. Basis: the operator chose to finish the contract-manifest ADR on 2026-10-14 to clear the orphan gate.

The accepted ADR `2026-10-13-startup-performance-operation-contract-manifest-adr` governs every Step. Its manifest model and lazy registry already exist in `src/cadrumo/application/operations/contract_manifest.py` with no consumer, which fails `dev/quality/tests/test_production_scan_surface_has_no_orphans.py`. This plan delivers the rest of its Implementation: the composition group table and shared inputs at the composition seam (S01), the dev generator, the generated `src/cadrumo/_data/operations/contract_manifest.json`, the drift recipe and its tests (S02), the manifest-backed registry for the worker with the module-graph gate (S03), and the runtime and terminal interface consumers (S04). The finding it answers is `import-bloat-worker` in `2026-10-13-startup-performance-audit`. No new costly decision is involved; group granularity follows the ADR's one group per owning operation module.

## Steps

- [x] `S01` - Split the monolithic production registry builder (operation_composition.py:1033-2145) into named composition groups, one per owning operation module, each importing its builders inside its function; move the shared composition inputs into one lazily resolving inputs object and keep build_production_operation_registry composing every group eagerly; `src/cadrumo/entrypoints/operation_composition.py`.
- [x] `S02` - Add the dev generator that composes the eager registry and writes the manifest through OperationContractManifestV1.from_registry (contract_manifest.py:118-133), generate the shipped manifest, add the generate and check recipes beside generate-provider-catalog (justfile:537-546), a drift test in the owning package and a planted-defect test proving the check fails on a stale manifest; `dev/operation_contract_manifest/generate.py, src/cadrumo/_data/operations/contract_manifest.json, justfile, src/cadrumo/entrypoints/tests/test_operation_contract_manifest.py`.
- [x] `S03` - Compose a manifest-backed registry (ManifestOperationRegistry.from_manifest, contract_manifest.py:166-172) over the group table and make the worker's compose_operation_dependencies (operation_composition.py:2148-2262, called from runtime/operation_host.py:183) use it; prove stale-manifest refusal and pin with a module-graph gate that reading every contract imports no operation handler module; `src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/entrypoints/tests/test_operation_contract_manifest.py`.
- [x] `S04` - Switch the runtime registry preparation (runtime/profile_connections.py:370) and the terminal interface registry door (tui/installed_session.py:336-343) to the manifest-backed registry, coordinating the runtime file with its active owner; `src/cadrumo/entrypoints/runtime/profile_connections.py, src/cadrumo/entrypoints/tui/installed_session.py`.

## Parallelization

Sequential. S02 needs the group table from S01; S03 needs the generated manifest from S02; S04 needs the manifest-backed registry from S03. S04 edits `src/cadrumo/entrypoints/runtime/profile_connections.py`, which another worker owns; that edit is coordinated through the orchestrator.

## Verification

- `dev/quality/tests/test_production_scan_surface_has_no_orphans.py` passes, so `contract_manifest.py` has a consumer.
- `just check-operation-contract-manifest` passes on the committed manifest and a planted-defect test shows it fails on a stale one.
- The owning-package drift test composes the eager registry and matches the shipped manifest, fingerprints included.
- A stale manifest makes the manifest-backed registry refuse when the group is composed.
- A module-graph gate shows reading every contract through the manifest-backed registry imports no operation handler module.
- Existing composition tests, ruff, `just check-types`, `just check-import-boundaries`, regenerated import-load targets and `dev/quality/tests/test_no_git_cli.py` pass.
