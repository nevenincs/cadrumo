---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S02'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
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
     The rerun the completeness-manifest drift gate and M303 registry build and record green after the base casillas join the manifest/construct and ## Scope

- `src/aeat/domain/calculations/registry/tests/test_record_design.py`
- `src/aeat/domain/calculations/registry/tests/test_record_design.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# rerun the completeness-manifest drift gate and M303 registry build and record green after the base casillas join the manifest/construct

## Scope

- `src/aeat/domain/calculations/registry/tests/test_record_design.py`
- `src/aeat/domain/calculations/registry/tests/test_record_design.py`

## Description

Reran the completeness-manifest drift gate and the M303 registry build after the
base casillas joined the manifest and construct.

## Outcome

`test_calculation_completeness_manifests_match_their_calculation_surface` passes for
M303 (the closure-only set 01/04/07/28 is resolved); the full
`test_record_design.py` plus the M303 registry, compensacion-carry, special-case
routing, and filing suites pass (425 passed, 0 failed). The long-standing M303
manifest-drift blocker is closed.

## Notes

The only remaining repository red is the pre-existing `test_tautology_gate` flag on
a committed peer iva-wallet test (hand-summed assertions), which is peer-owned and
outside this feature's surface.
