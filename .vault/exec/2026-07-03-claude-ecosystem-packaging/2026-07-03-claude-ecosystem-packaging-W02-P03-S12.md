---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S12'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Keep the _data size-budget gate meaningful per distribution after the split so the budget is not evaded by moving bytes to the companion and ## Scope

- `src/aeat/tests/test_data_size_budget.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Keep the _data size-budget gate meaningful per distribution after the split so the budget is not evaded by moving bytes to the companion

## Scope

- `src/aeat/tests/test_data_size_budget.py`

## Description

- Update `test_data_size_budget.py` to keep the pre-existing 550 MiB total `_data` budget gate.
- Add per-distribution ceilings: a 230 MiB runtime-slice ceiling (measured ~173 MiB) and a 380 MiB companion-slice ceiling (measured ~312 MiB).
- Add an exhaustive-partition assertion so the split cannot silently move bytes out of the budgeted set to evade the gate.
- Commit `815efad31d`.

## Outcome

- 5/5 tests passed.

## Notes

No incidents. No skipped work.
