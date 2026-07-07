---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-07'
step_id: 'S347'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S347 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The Annotate stale overview explain deadlines and ## Scope

- `add an out-of-plazo annotation to explain output when overview calendar would have closed >12 months ago`
- `src/aeat/application/overview/_explain.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Annotate stale overview explain deadlines

## Scope

- `add an out-of-plazo annotation to explain output when overview calendar would have closed >12 months ago`
- `src/aeat/application/overview/_explain.py`

## Description

- Grounded the S347 finding with vault and code RAG searches for overview
  explain, stale deadlines, out-of-plazo, and prescription warnings.
- Checked the live BOE LGT authority for the ordinary four-year prescription
  framing in Ley 58/2003 arts. 66-67.
- Added `out_of_plazo_warning` to the typed `OverviewExplain` application
  payload.
- Derived the warning from the same registry deadline windows used by the
  deadline engine, preserving the existing applicability verdict.
- Rendered the warning in overview explain text output.
- Added real-registry tests for Modelo 100 2022 and 2025 deadline windows.

## Outcome

Closed. `overview explain` can now say both things that are true for a stale
historical return:

- the taxpayer-model applicability verdict remains `APPLICABLE`; and
- the voluntary filing window closed more than twelve months ago, with the
  ordinary four-year LGT arts. 66-67 horizon named.

For the S347 repro shape, Modelo 100 tax year 2022 evaluated on 2026-07-07
returns `applicable=True` and carries:

`out_of_plazo: voluntary filing window closed on 2023-06-30; as of 2026-07-07 the return is 1103 days past the deadline and is inside the ordinary four-year LGT arts. 66-67 prescription horizon (ordinary boundary 2027-06-30).`

Recent windows do not get the warning: Modelo 100 tax year 2025 evaluated on
2026-07-07 is after its 2026-06-30 close, but not more than twelve months past
the voluntary deadline.

Validation:

- `uv run --no-sync pytest -q src/aeat/application/overview/tests/test_explain.py`
  passed: 14 tests.
- `uv run --no-sync ruff check src/aeat/application/overview/_explain.py src/aeat/application/overview/tests/test_explain.py src/aeat/entrypoints/cli/_overview_rendering.py`
  passed.
- A direct `build_overview_explain` sanity check for Modelo 100 2022 returned
  `applicable=True` plus the out-of-plazo warning.

## Notes

No deadline dates were hard-coded. The warning reads the validated registry
deadline windows and only annotates matching windows whose close date is at
least twelve months behind the reference date.
