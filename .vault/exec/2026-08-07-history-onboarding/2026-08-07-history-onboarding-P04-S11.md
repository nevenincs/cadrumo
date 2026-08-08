---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a91a6ecb13f4658e153077e25e79a3ecc4d22edcaa5486a14e9475f4dc85aa33'
step_id: 'S11'
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
     The S11 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The add the overview INFO Notice naming aeat app live filed pull-all when a workable profile has zero observations carrying an official ObservationSourceKind, verified by a calendar-overview test asserting the Notice fires for a zero-observation profile and is absent once one official observation exists and ## Scope

- `src/cadrumo/application/overview/_calendar_evidence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the overview INFO Notice naming aeat app live filed pull-all when a workable profile has zero observations carrying an official ObservationSourceKind, verified by a calendar-overview test asserting the Notice fires for a zero-observation profile and is absent once one official observation exists

## Scope

- `src/cadrumo/application/overview/_calendar_evidence.py`

## Description

- Add `no_aeat_history_notice` and its code, promoted through the existing calendar re-export onto the overview facade.

## Outcome

Keyed on official-source membership rather than on an empty observation list, and
that choice is the substance of the row. A profile whose only observations are
locally filed or operator-entered has exactly the same gap as one with no
observations at all — it holds nothing AEAT ever confirmed — so testing for
emptiness would leave precisely that taxpayer unprompted.

An unrecognised source token fails closed and still prompts, rather than silently
telling the operator they are done.

## Verification

uv run --no-sync pytest src/cadrumo/application/overview/tests/test_no_aeat_history_notice.py -q -n0
    8 passed in 3.15s

The official and non-official arms are each driven from the live enum with a
non-empty anchor assertion, so neither can pass vacuously if the taxonomy changes
shape.

## Notes

Routed through the existing `_calendar` re-export because the overview facade
already sources its sibling evidence function that way; adding a second import
path for one function would have been the inconsistency, not the fix.
