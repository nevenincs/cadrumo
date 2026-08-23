---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:dc09282a944222160c6d2890a6d9720d048235761eb95a44f7a8e0836a2ef8ae'
step_id: 'S40'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S40 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The enroll the inventory resolver and explicit source disposition and ## Scope

- `src/cadrumo/application/aggregation/_source_mesh.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# enroll the inventory resolver and explicit source disposition

## Scope

- `src/cadrumo/application/aggregation/_source_mesh.py`

## Description

- Promote inventory from deferred to enrolled in the canonical calculation-route ownership catalogue.
- Export only the public inventory resolver through the aggregation facade.
- Preserve runtime repository construction and invocation for S41.
- Add route-derived enrollment, disposition, uniqueness, discovery, and missing-source parity tests.

## Outcome

Inventory now has one canonical mesh-stage owner, resolver identity `inventory`, and an enrolled route disposition. It is absent from the deferred set, publicly discoverable through the aggregation facade, and covered by the existing total-disjoint disposition partition. The live runtime does not yet construct or invoke the repository resolver; that orchestration remains explicitly assigned to S41.

The implementation updates no census status, registry bindings, caller-override policy, or calculation persistence. Allocation-free no-binding behavior, value-free diagnostics, sealed source provenance, and retained conflict advisories remain owned by the S39 resolver.

Independent review reported zero findings. Fifty-eight focused tests passed and Ruff and scoped diff hygiene were clean.

## Notes

Grounding showed that `_source_mesh.py` owns deferred classification while `_calculation_route.py` owns canonical resolver-stage enrollment. The approved S40 scope expanded minimally to the route catalogue and aggregation facade; `_calculation_actions.py` remains untouched.

The type-check gate is not clean repository-wide: the shared tree currently reports 1,257 unrelated diagnostics, and a narrow invocation exposes pre-existing `_calculation_route.py` protocol and `ModeloCalculationRouteId` diagnostics. Review found no S40-specific type regression. This baseline was recorded rather than broadened into unrelated repair.
