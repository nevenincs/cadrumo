---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Drive the caller-override rejection ladder guard code from the declared tier data rather than sequential inline guards and ## Scope

- `src/aeat/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Drive the caller-override rejection ladder guard code from the declared tier data rather than sequential inline guards

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Derive `BUCKET_AGGREGATION_LOCK_SOURCES` and `CALLER_OVERRIDABLE_CARRY_SOURCES` from the ladder in the calculation source policy, removing the hand-listed frozensets.

## Outcome

The two caller-override guard invocations consume ladder-derived sets; a source kind's lock-vs-carry disposition is declared once. Identical membership (8 lock, 3 carry). Commit `ddda33609`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
