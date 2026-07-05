---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S08'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cpdefix-followup-allgreen with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-05-cpdefix-followup-allgreen-plan placeholders are machine-filled by
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
     The Run focused gates for import hygiene, source enrollment, M720 row carrier, and M347 counterpart-summary behavior and ## Scope

- `src/aeat/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run focused gates for import hygiene, source enrollment, M720 row carrier, and M347 counterpart-summary behavior

## Scope

- `src/aeat/tests/`

## Description

- Rebaselined against HEAD `c0f82c0b17` after concurrent registry and documentation consolidation commits.
- Reran RAG code discovery for M347 invoice-owned summary bindings, M720 foreign-asset row binding values, and deferred/reserved source-mesh disposition.
- Confirmed with exact grep that M347 summary bindings remain `collectible_invoice`, M720 row binding carriers remain present, and the source mesh still declares deferred and reserved partitions.
- Ran the focused import hygiene, M720 row-carrier, M347 counterpart-summary, and source-enrollment gate set sequentially with `-n 0`.

## Outcome

Focused gates are green at current HEAD.

Verification passed:

`uv run --no-sync pytest -q -n 0 src/aeat/tests/test_import_hygiene_gate.py src/aeat/application/aggregation/tests/test_foreign_assets.py src/aeat/application/modelo/tests/test_calculation_resolution.py src/aeat/application/modelo/tests/test_revision_replay_inputs.py src/aeat/application/aggregation/tests/test_source_mesh.py src/aeat/application/aggregation/tests/test_source_mesh_readiness.py src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py src/aeat/application/aggregation/tests/test_per_modelo_service.py src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py src/aeat/application/modelo/tests/test_source_mesh_missing_sources.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py --tb=short`

Result: 125 passed in 59.86s.

No source code was edited for this gate step.

## Notes

- These focused gates support the cpdefix follow-up tracker only. They are not a full-tree allgreen claim.
- The prior S08 scaffold evidence has been superseded by this current-HEAD rerun.
