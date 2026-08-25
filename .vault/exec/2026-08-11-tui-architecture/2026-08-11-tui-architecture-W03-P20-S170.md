---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6c694d2657a6c974c2ee5cb2bb236f5b5983c4b169368bb36c77dfeb90cab5de'
step_id: 'S170'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S170 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Hard-move the complete public Modelo work-addressing and ModeloWorkResolution contract into the sole defining module application/modelo/work_addressing.py, delete private _work_addressing.py and only the work-selector family from _selectors.py, and leave the application/modelo package namespace inert with no re-exports, replacing every work selector with one pure operation over a caller-supplied WorkUnitCatalogue and already-resolved bucket that explicitly separates visible natural all-state reads (zero is ABSENT, one active or discarded unit is RESOLVED, and every multiple set is ambiguous), strict full-WorkUnitId all-state reads (absence refuses and a discarded singleton resolves), operator-only 12-character prefix-or-suffix lookup with deterministic full-ID ordering and ambiguity refusal, and natural active-only create-or-reuse semantics filtered before the same cardinality policy, with all target-coordinate and stored-work revision assertions evaluated only after cardinality and never used to narrow candidates, atomically converge work review, external import, the overview application and CLI producer, calculation, history, reconcile, taxation comparison, workflow/resume, lifecycle, and every static, local, TYPE_CHECKING, annotation, registration, dynamic, test, fixture, and tooling consumer on direct defining-module imports while preserving only constraint-divergent lifecycle admission and typed error/precondition translations as delegating boundary wrappers, delete every selector-owned repository read and every parallel, substitutable, or repository-owning catalogue scan or first-match pick while retaining the sole canonical pure scan over the supplied catalogue, delete every package/private alias, shim, compatibility or fallback path, prove with real encrypted-SQL post-capture mutation that selection remains on the captured record and performs no second SELECT, and enforce current-HEAD exact-AST plus Vaultspec-RAG semantic fixed-point gates for one definition, complete consumer convergence, and zero remnant or parallel selector/read authority and ## Scope

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
- `and exact AST/Vaultspec-RAG fixed-point tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
