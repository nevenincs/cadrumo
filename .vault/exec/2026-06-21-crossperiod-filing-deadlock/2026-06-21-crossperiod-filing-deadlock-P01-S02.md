---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S02'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace crossperiod-filing-deadlock with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Guard the target-year compute against NoDeadlineWindowsError so a year with no registry windows degrades to NO_PENDING_OBLIGATION rather than UNHANDLED_EXCEPTION and ## Scope

- `src/aeat/application/workflow/_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Guard the target-year compute against NoDeadlineWindowsError so a year with no registry windows degrades to NO_PENDING_OBLIGATION rather than UNHANDLED_EXCEPTION

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- Wrap the target-year `compute` in `try/except NoDeadlineWindowsError`, falling back to the as-of-today schedule so a target filing year with no registry windows degrades to `NO_PENDING_OBLIGATION` at the absent-target filter rather than `UNHANDLED_EXCEPTION`.
- Import `NoDeadlineWindowsError` from `...domain.deadlines`.

## Outcome

Landed in commit `6e635f566`. Fixes `test_gate_aborts_when_projection_lacks_the_target`; a never-existing obligation still refuses `NO_PENDING_OBLIGATION`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
