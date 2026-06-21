---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S01'
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
     The S01 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Re-scope the FILE-gate obligation schedule to the target period's filing year for an explicit FILE target, leaving the as-of-today projection on today.year and ## Scope

- `src/aeat/application/workflow/_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-scope the FILE-gate obligation schedule to the target period's filing year for an explicit FILE target, leaving the as-of-today projection on today.year

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- Branch the `_stage_computing_deadlines` schedule resolution: for a `WorkflowPurpose.FILE` with an explicit `target_modelo`/`target_period` whose `filing_year != today.year`, call `self._deadline_engine.compute(profile, target_period.filing_year, today=today)` instead of `compute_obligation_schedule(today)`.
- Keep the common branch (and the as-of-today `pending_obligations` projection) on `today.year`, preserving the single-producer invariant.

## Outcome

Landed in commit `6e635f566`. A 2024 1T obligation is now found in the 2024 schedule under a 2026 clock and classified OVERDUE. `test_engine.py` 47/47 green; the as-of-today projection invariant is unchanged.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
