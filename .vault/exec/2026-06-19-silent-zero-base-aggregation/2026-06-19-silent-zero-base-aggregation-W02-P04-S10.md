---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S10'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
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
     The add an annual M100 actividad-económica income aggregator (annual window, actividad eligibility) mirroring the first-slice expense pipeline shape and ## Scope

- `src/aeat/application/aggregation/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add an annual M100 actividad-económica income aggregator (annual window, actividad eligibility) mirroring the first-slice expense pipeline shape

## Scope

- `src/aeat/application/aggregation/`

## Description

Added an annual Modelo 100 actividad-económica income aggregator, the counterpart
of the M130 cumulative-quarter income path.

- `aggregate_renta_m100_income_ledger(_from_repositories)` in
  `src/aeat/application/aggregation/_renta_income_ledger.py`: full-ejercicio window
  (Jan 1 to Dec 31 of the period year), reuses `_classify_income_transaction`
  (same actividad eligibility, excludes nómina/personal), re-targets each eligible
  observation to the M100 income leaf 0171, and builds an M100 casilla aggregation.
- Rejects a non-annual period with `AggregationPeriodError`.

## Outcome

Unit tests in `test_renta_income_aggregation.py` cover the annual window (in-year
receipts summed into 0171, prior-year excluded) and the non-annual refusal; 21
income tests pass. The M130 quarterly path is untouched.

## Notes

None.
