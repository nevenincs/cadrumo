---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S03'
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
     The S03 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Admit an explicitly-targeted overdue obligation as a late local filing, stamping the extemporanea marker on the COMPUTING_DEADLINES step details instead of aborting DEADLINE_PASSED and ## Scope

- `src/aeat/application/workflow/_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Admit an explicitly-targeted overdue obligation as a late local filing, stamping the extemporanea marker on the COMPUTING_DEADLINES step details instead of aborting DEADLINE_PASSED

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- In the `obligation.closes_on < today` branch, when `target_modelo`/`target_period` are present, append a successful `COMPUTING_DEADLINES` `WorkflowStep` carrying `overdue=true`/`extemporanea=true` plus the modelo/period/closes_on details, and `return obligation` instead of falling through to the `DEADLINE_PASSED` abort.
- Keep the non-targeted path on the original `DEADLINE_PASSED` abort.

## Outcome

Landed in commit `6e635f566`. The late LOCAL `work file` is admitted and persists the `app_filing` carry observation; `work file` contacts AEAT zero times. Reuses the existing registry-grounded `Recovery` (Ley 58/2003 art-27) admissibility. `test_deadline_passed_via_run_for_period` updated and green.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
