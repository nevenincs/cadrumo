---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6efd580ae49be1cd40f588f5105f957691725740b23f30b06dc704fed3d2d0bd'
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
- Prove capture-then-mutate selection against encrypted SQL statement instrumentation and add exact-AST fixed-point assertions for the public owner, removals, package inertness, scan replacements, and boundary consumers.

## Outcome

- The pure selector accepts only a caller-supplied `WorkUnitCatalogue` and resolved bucket, with visible, strict-id, operator 12-character, and active-natural cardinality semantics owned by one public module.
- Targeted compilation and Ruff passed. The boundary translation plus selector matrix passed 19 tests, and the expanded exact-AST fixed-point test passed.
- Independent review passed in audit commit `4b802cc588`, with no remaining S170 finding.
- After the directory-scan relocation landed, the post-review live rerun completed 73 tests in 194.37 seconds: 73 passed and one external auth-relocation import failed before S170 selector/review work. The sole failure was `ModuleNotFoundError` for `cadrumo.adapters.outbound.aeat.auth.session_probe` on the provider-selection to clave-movil path.
- The current exact AST census and scoped Ruff gate passed after the review evidence was recorded.
- A fresh code RAG index placed all semantic positive matches for the selector owner in `work_addressing.py`. Its current shared corpus reported incomplete coverage, so the exact AST census, rather than semantic absence, proves the zero-remnant result.

## Notes

- The post-review external auth-relocation failure is outside the S170 surface and has not been changed here.
- S170 is eligible for the coordinating plan lifecycle transition because the independent review passed and the current S170 exact census and Ruff gate are green.
