---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:abef2380c6c343ef018e294fa49db9a4f68e22af602567a1e91c3eedd90658b9'
step_id: 'S42'
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
     The S42 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The enforce inventory source ownership and caller-override refusal and ## Scope

- `src/cadrumo/application/modelo/_calculate_input.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# enforce inventory source ownership and caller-override refusal

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Add inventory to the canonical deterministic source-ownership lock ladder.
- Derive binding and bound-casilla collisions from registry selectors through the existing calculation guard.
- Refuse equal, different, partial, complete, and alias caller substitutions while preserving undeclared manual input.
- Update conformance truth and add replay-stable ownership tests.

## Outcome

Inventory is now a deterministic source-owned family in the single canonical caller-override precedence ladder. The calculation policy derives its lock set from that ladder, and the existing calculation guard derives exact owned binding and bound-casilla identities from the active registry revision. Caller values therefore cannot collide with, replace, shadow, or silently equal an inventory-derived output.

The policy contains no hard-coded inventory casilla map. When a revision does not declare inventory bindings, its manual casillas remain available under the standing absence policy. Non-canonical aliases refuse at registry input validation before ownership matching, and repeated identical requests produce the same typed, value-free outcome.

Independent review reported zero findings. Twenty-one focused tests passed, and Ruff, the focused type checker, and scoped diff hygiene were clean.

## Notes

Grounding showed that the plan's `_calculate_input.py` target was not the policy authority: it parses typed channels but has no source-ownership context. The approved implementation redirected to `_source_mesh.py::CALLER_OVERRIDE_PRECEDENCE_LADDER`; `_calculation_source_policy.py` and `_calculation_actions.py` already project and enforce that single home. No `_calculate_input.py` edit or S43 binding data was added.

An exploratory existing `test_actions` source-bound fixture is red because its IVA selector omits newer required fields; a broader M349 exploratory failure was also unrelated. Neither belongs to S42, and both were left untouched.
