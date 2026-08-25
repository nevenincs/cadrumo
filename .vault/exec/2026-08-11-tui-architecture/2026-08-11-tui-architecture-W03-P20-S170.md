---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6de0df9e4b9e82d79335bc663d198a0963acf7517c07e4d9f128c9434ab9807a'
step_id: 'S170'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Modelo work-addressing selector convergence

## Scope

- Promote the sole public Modelo work-addressing contract and captured-catalogue selector.
- Delete the former private addressing and draft selector modules, remove moved package exports, and converge direct consumers.
- Preserve lifecycle and boundary-specific policies while proving pure selection and capture behavior.

## Description

- Promote the complete Modelo work-addressing contract and the sole pure supplied-catalogue selector to `work_addressing.py`.
- Delete the former private addressing module, the draft selector module, package re-exports, and the retired work-selector family while retaining calculation-revision policy in `_selectors.py`.
- Converge direct import consumers, including review, external import, overview, calculation, history, reconciliation, taxation, workflow, CLI, registry, and tests.
- Record the shared move/deletion/import sweep in commit `5dcd5a9c026` and boundary hardening in commit `82c906562d`.
- Preserve boundary translations: history maps malformed caller ids to its established not-found error; reconciliation maps strict-id absence to its established not-found error and rejects a known cross-bucket id before scoped selection.
- Prove capture-then-mutate selection against encrypted SQL statement instrumentation and enforce the public owner, removals, inert package, direct consumers, dynamic access, dataflow wrappers, and retired text through the reusable canonical import-authority scanner.

## Outcome

- The pure selector accepts only a caller-supplied `WorkUnitCatalogue` and resolved bucket, with visible, strict-id, operator 12-character, and active-natural cardinality semantics owned by one public module.
- Targeted compilation and Ruff passed. The boundary translation plus selector matrix passed 19 tests, and the expanded exact-AST fixed-point test passed.
- The review PASS at `4b802cc588` over frozen source `a3dbaeee421` was superseded by the final integrated review recorded in `2026-08-25-tui-architecture-s170-remediation-review-audit`; it did not prove complete tracked-live discovery or the dynamic and semantic authority shapes required by S170.
- After the directory-scan relocation landed, the post-review live rerun completed 73 tests in 194.37 seconds: 73 passed and one external auth-relocation import failed before S170 selector/review work. The sole failure was `ModuleNotFoundError` for `cadrumo.adapters.outbound.aeat.auth.session_probe` on the provider-selection to clave-movil path.
- The corrective fixed-point gates share one reusable scanner over the complete tracked-live inventory, and their exact mutants cover relative imports, aliases, module and local dataflow, dynamic imports and exports, indirect export maps, nested definitions, and realistic repository-owned selector wrappers.
- The resident-service discovery gate classifies every returned production owner, requires the sole canonical `work_addressing.py` result, rejects mixed canonical-plus-parallel results, and runs through the standard resident-service lane.

## Notes

- The post-review external auth-relocation failure is outside the S170 surface and has not been changed here.
- S170 remains unchecked after the false PASS was retracted. The atomic remediation requires an independent clean-HEAD review before any lifecycle transition.
