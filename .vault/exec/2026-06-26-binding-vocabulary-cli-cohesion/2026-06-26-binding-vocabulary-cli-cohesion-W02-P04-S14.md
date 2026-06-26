---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S14'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Verify W02.P04 no-shift: run pytest --collect-only -q clean, the aggregation / filing-runtime test modules green, and assert ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions were NOT renamed (the phase-2.2 settled contract is intact) and ## Scope

- `src/aeat/application/aggregation/tests`
- `src/aeat/application/filing/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify W02.P04 no-shift: run pytest --collect-only -q clean, the aggregation / filing-runtime test modules green, and assert ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions were NOT renamed (the phase-2.2 settled contract is intact)

## Scope

- `src/aeat/application/aggregation/tests`
- `src/aeat/application/filing/tests`

## Description

- Assert the settled phase-2.2 `ModeloSourceResolver` protocol, `CalculationSourceResolution` envelope, and `merge_source_resolutions` aggregate are NOT renamed and still present at their original definitions in `_source_mesh.py`.
- Run the aggregation-service, source-mesh, source-resolver-enrollment, and filing-runtime test modules plus the bindings-framework gate suite.

## Outcome

W02.P04 no-shift proven. The settled resolver contract is intact (the protocol, the output envelope, and both merge functions all present at their original locations). collect-only clean (16463). The aggregation / mesh / enrollment tests ran 69 passed and the bindings-framework gate suite ran 49 passed (with the 98 across earlier W02 steps); the filing tests ran 230 passed under S13.

## Notes

None.
