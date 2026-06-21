---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S04'
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
     The S04 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Skip the submission filing-window preflight for the local FILE purpose alongside VERIFY and ## Scope

- `src/aeat/application/workflow/_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Skip the submission filing-window preflight for the local FILE purpose alongside VERIFY

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- Replace `skip_deadline_window=purpose is WorkflowPurpose.VERIFY` with `skip_window = purpose in (WorkflowPurpose.VERIFY, WorkflowPurpose.FILE)` on the submission preflight, since FILE is a LOCAL mark-as-filed that contacts AEAT zero times and its obligation existence is already enforced at the deadline stage.
- Document inline why re-applying the submission window gate would re-block the legitimate late local filing.

## Outcome

Landed in commit `6e635f566`. Fixes `test_verify_reaches_done_for_a_closed_filing_window`. The window gate now binds only an actual AEAT submission, which this app never performs.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
