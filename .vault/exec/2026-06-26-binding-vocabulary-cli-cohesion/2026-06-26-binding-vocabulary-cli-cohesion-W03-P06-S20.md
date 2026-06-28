---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S20'
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
     The S20 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Verify W03.P06 no-shift: run pytest --collect-only -q clean and assert the prefill modules retain distinct names and tiers with no merge and no behaviour change (docstring-only clarification) and ## Scope

- `src/aeat/application/calculations/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify W03.P06 no-shift: run pytest --collect-only -q clean and assert the prefill modules retain distinct names and tiers with no merge and no behaviour change (docstring-only clarification)

## Scope

- `src/aeat/application/calculations/tests`

## Description

- Assert the three prefill modules retain distinct names and tiers with no merge: the relation resolver in the relation prefill module, the `previous_filing` carry in the binding prefill module, and the `aeat_prefilled` flag in the registry schema.
- Run the application calculations test suite.

## Outcome

W03.P06 no-shift proven. The three prefill tiers remain distinct (the relation prefill module owns the relation resolver, the binding prefill module carries 16 `previous_filing` references, and the registry schema owns the `aeat_prefilled` flag), with no merge and no behaviour change (docstring/comment-only clarification). The application calculations test suite ran 401 passed.

## Notes

None.
