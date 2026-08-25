---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:440b63a5db5e95e761b53813b277a842adcd0242228851ae3500b10e31e98e73'
step_id: 'S170'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move the complete public Modelo work-addressing and ModeloWorkResolution contract into the sole defining module application/modelo/work_addressing.py, delete private _work_addressing.py and only the work-selector family from _selectors.py, and leave the application/modelo package namespace inert with no re-exports, replacing every work selector with one pure operation over a caller-supplied WorkUnitCatalogue and already-resolved bucket that explicitly separates visible natural all-state reads (zero is ABSENT, one active or discarded unit is RESOLVED, and every multiple set is ambiguous), strict full-WorkUnitId all-state reads (absence refuses and a discarded singleton resolves), operator-only 12-character prefix-or-suffix lookup with deterministic full-ID ordering and ambiguity refusal, and natural active-only create-or-reuse semantics filtered before the same cardinality policy, with all target-coordinate and stored-work revision assertions evaluated only after cardinality and never used to narrow candidates, atomically converge work review, external import, the overview application and CLI producer, calculation, history, reconcile, taxation comparison, workflow/resume, lifecycle, and every static, local, TYPE_CHECKING, annotation, registration, dynamic, test, fixture, and tooling consumer on direct defining-module imports while preserving only constraint-divergent lifecycle admission and typed error/precondition translations as delegating boundary wrappers, delete every selector-owned repository read and every parallel, substitutable, or repository-owning catalogue scan or first-match pick while retaining the sole canonical pure scan over the supplied catalogue, delete every package/private alias, shim, compatibility or fallback path, prove with real encrypted-SQL post-capture mutation that selection remains on the captured record and performs no second SELECT, and enforce current-HEAD exact-AST plus Vaultspec-RAG semantic fixed-point gates for one definition, complete consumer convergence, and zero remnant or parallel selector/read authority

## Scope

- `src/cadrumo/application/modelo/work_addressing.py`
- `retired src/cadrumo/application/modelo/_work_addressing.py`
- `work-selector family only in src/cadrumo/application/modelo/_selectors.py`
- `src/cadrumo/application/modelo/__init__.py`
- `src/cadrumo/application/modelo/work_review_projection.py`
- `src/cadrumo/application/modelo/_external_import_actions.py`
- `src/cadrumo/application/overview/_data_prep.py`
- `src/cadrumo/entrypoints/cli/_overview.py`
- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/application/modelo/_history.py`
- `src/cadrumo/application/modelo/_reconcile.py`
- `src/cadrumo/application/modelo/_taxation_comparison.py`
- `src/cadrumo/application/modelo/_work_lifecycle.py`
- `src/cadrumo/application/workflow/resume.py`
- `every affected application/entrypoint/dev/test/fixture/TYPE_CHECKING/annotation/registration/dynamic/tooling consumer`
- `focused pure-selector and real encrypted-SQL post-capture/no-second-SELECT tests`
- `dev/quality/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_gate.py`
- `and exact AST/Vaultspec-RAG fixed-point tests`

## Description

- Promote the complete Modelo work-addressing contract and the sole pure supplied-catalogue selector to `work_addressing.py`.
- Delete the former private addressing module, the draft selector module, package re-exports, and the retired work-selector family while retaining calculation-revision policy in `_selectors.py`.
- Converge direct import consumers, including review, external import, overview, calculation, history, reconciliation, taxation, workflow, CLI, registry, and tests.
- Record the shared move/deletion/import sweep in commit `5dcd5a9c026`.
- Preserve boundary translations: history maps malformed caller ids to its established not-found error; reconciliation maps strict-id absence to its established not-found error and rejects a known cross-bucket id before scoped selection.
- Prove capture-then-mutate selection against encrypted SQL statement instrumentation and add exact-AST fixed-point assertions for the public owner, removals, package inertness, scan replacements, and boundary consumers.

## Outcome

- The pure selector accepts only a caller-supplied `WorkUnitCatalogue` and resolved bucket, with visible, strict-id, operator 12-character, and active-natural cardinality semantics owned by one public module.
- Targeted compilation and Ruff passed. The boundary translation plus selector matrix passed 19 tests, and the expanded exact-AST fixed-point test passed.
- A fresh code RAG index completed and placed all semantic positive matches for the selector owner in `work_addressing.py`. Its current shared corpus reports incomplete coverage, so the exact AST census, rather than semantic absence, proves the zero-remnant result.
- The scoped gate reran Ruff and the fixed-point test successfully. The wider consumer collection was attempted but is separately blocked by concurrent core relocation work.

## Notes

- The expanded focused consumer suite was blocked before collection by concurrent core relocation work: `cadrumo.core.__getattr__` still names deleted `_directory_scan` while the replacement is uncommitted. This is outside the S170 surface; no directory-scan change was made here.
- The plan remains open pending the required independent review.
