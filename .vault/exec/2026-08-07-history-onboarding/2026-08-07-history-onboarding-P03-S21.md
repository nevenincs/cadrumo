---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c09487dc7d067f0f18285c680ecb5242cf43ddcc02c594757ab22c195caf9c4e'
step_id: 'S21'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The extend FiledDataCaptureReport and BulkFiledDataCaptureReport with a per modelo ejercicio period breakdown of raw register row count versus the one persisted calculation observation, computed from the declarations and selected tuples already held before finalize_filed_capture runs, touching no persistence-boundary file, verified by a synthetic-fixture test asserting a two-row period reports raw count two and selected count one and ## Scope

- `src/cadrumo/application/live/_filed_data_capture.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# extend FiledDataCaptureReport and BulkFiledDataCaptureReport with a per modelo ejercicio period breakdown of raw register row count versus the one persisted calculation observation, computed from the declarations and selected tuples already held before finalize_filed_capture runs, touching no persistence-boundary file, verified by a synthetic-fixture test asserting a two-row period reports raw count two and selected count one

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `FiledPeriodSelectionRow` and `filed_period_selection_rows`, projecting raw register rows against captured observations.

## Outcome

The register can hold several filings for one period and exactly one is promoted
to calculation history. That collapse is correct and was invisible, so an operator
seeing one persisted observation could not tell whether AEAT held one filing or
four.

Keyed on PERIOD rather than on the query pair, because one pair returns several
periods and summing them would report the pair as duplicated while hiding which
period actually held two filings.

Supersession is read off the raw count alone. Deriving it from raw-minus-selected
conflates a period AEAT held several filings for with a period whose single filing
simply was not captured — and reporting the second as supersession would tell the
operator their filing was superseded by one that never existed. The unaccounted
rows get their own count instead.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_discovery.py -q -n0
    38 passed in 16.82s

The period-keying test caught a real semantic defect on first run: a period with
one uncaptured row reported `held_more_than_one_filing` as true. The predicate was
corrected to the raw count, which is also what the sibling advisory row specifies.

## Notes

Computed from tuples the sweep already holds before finalisation, so it touches no
persistence-boundary file and adds no read.
