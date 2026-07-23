---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S03'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Author the strict frozen FlowDefinition family (flow, section, page, choice, copy-reference, branching predicate, repeating group, compare-select) with build-time validators for unique ids, forward-only references, and reference-not-literal copy slots and ## Scope

- `src/cadrumo/application/flows/_definition.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the strict frozen FlowDefinition family (flow, section, page, choice, copy-reference, branching predicate, repeating group, compare-select) with build-time validators for unique ids, forward-only references, and reference-not-literal copy slots

## Scope

- `src/cadrumo/application/flows/_definition.py`

## Description

- Author the strict frozen FlowDefinition family (flow, section, page, choice, copy reference, condition/visibility, repeating group) with build-time validators: unique ids, forward-only gate references, choice-widget coherence, compare-select provenance, reserved defer token, count-source typing, per-mode checkpoint coverage.
- Land in commit 91c5e51afc; fingerprint docstring corrected in 9b03c2180d.

## Outcome

Definition contract enforced at model construction; the real 11-section setup catalogue validates through it.

## Notes

Copy slots are references only; literal prose is structurally unrepresentable.
