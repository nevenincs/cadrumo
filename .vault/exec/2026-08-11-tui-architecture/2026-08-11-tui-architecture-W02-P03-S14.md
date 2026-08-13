---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c60b24a076d6e4a0d9ce3767664aad002aa139b480c28d1061692a807ac19384'
step_id: 'S14'
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
     The S14 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Implement operation definition registration and immutable lookup by canonical action reference and ## Scope

- `src/cadrumo/application/operations/_registry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement operation definition registration and immutable lookup by canonical action reference

## Scope

- `src/cadrumo/application/operations/_registry.py`

## Description

- Define immutable operation definitions binding model families, executor construction, phases, interactions, capabilities, and an optional canonical action reference.
- Canonicalize registry order and refuse duplicate operation or action identities.
- Expose fail-closed lookup by operation definition ID and canonical `ActionReference`.
- Evolve the sole public facade and its exact import-boundary proof.
- Declare closed reconciliation and permitted-frontend axes without importing any frontend.
- Bind each definition to a non-effectful executor descriptor that correlates its request model, structural executor type, and validated construction result.

## Outcome

`OperationRegistry` is the single generic definition registry. It stores immutable, sorted definitions and performs an optional identity-only join to the existing operator-action authority without copying its catalogue entries, command targets, arguments, or resolution policy.

Focused verification passed:

- `uv run ruff check src/cadrumo/application/operations/_registry.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_registry.py src/cadrumo/application/operations/tests/test_facade.py` - passed.
- `uv run basedpyright src/cadrumo/application/operations/_registry.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_registry.py` - 0 errors, 0 warnings, 0 notes.
- `uv run pytest -q -n 0 src/cadrumo/application/operations/tests/test_registry.py src/cadrumo/application/operations/tests/test_facade.py` - 5 passed in 0.88 seconds.
- After completeness remediation, the same Ruff and basedpyright scopes passed and the focused pytest command passed 7 tests in 0.87 seconds.
- `uvx vaultspec-core vault check all` completed successfully during closeout with 1,353 repository warnings and no failing check.

## Notes

Live code semantic search returned the operation models, capabilities, interactions, executor contracts, sole facade, and canonical `ActionCatalogue` as the ownership cluster. Vault search returned D6, the binding plan, and research. Whole-file reads covered `operator_actions._models`, `operator_actions._catalogue`, `operator_surface._action_resolution`, operation models, and the governing ADR and plan; targeted `rg` covered action references, catalogues, resolution, and operation definitions because the code index reported nine missing sections. No generic operation registry existed. The new join retains `ActionReference` identity only and deliberately does not redeclare the operator-action catalogue or its live-command resolver.

The first focused pytest correctly exposed the exact facade import-set expectation; it was updated to admit only the new canonical `_registry` owner and the final gate passed. S15 remains the owner of fixed-point catalogue/surface reconciliation, and S16 remains the owner of broader executor refusal conformance.

Review found D6 completeness gaps around reconciliation, frontend projections, and factory correlation. A fresh semantic and exact sweep found no operation-level superset authority: operator-surface reconciliation describes command projection rather than owner-loss recovery, and entrypoint-specific exposure declarations are not generic operation policy. `OperationReconciliationPolicy` and `OperationFrontendProjection` therefore live narrowly in the operation registry and carry identities only. `OperationExecutorFactory` is a frozen descriptor: registration checks the declared executor class structurally without instantiation, definition validation binds the exact request model, and `create()` validates the constructed object before supervisor use without executing the operation.
