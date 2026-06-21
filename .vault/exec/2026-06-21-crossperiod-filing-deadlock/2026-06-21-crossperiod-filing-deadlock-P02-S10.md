---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S10'
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
     The S10 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Reconcile the local cross-period carry tests to admit-with-advisory for same-year chains while keeping the cross-year prior blocking and preserving the app_filing-non-official invariant and ## Scope

- `src/aeat/application/modelo/tests/test_local_cross_period_carry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Reconcile the local cross-period carry tests to admit-with-advisory for same-year chains while keeping the cross-year prior blocking and preserving the app_filing-non-official invariant

## Scope

- `src/aeat/application/modelo/tests/test_local_cross_period_carry.py`

## Description

- Reconcile `test_local_cross_period_carry.py`: the same-year case now asserts admit-with-advisory (the non-official-local-chain advisory surfaces and verify grants), and asserts the cross-year dependency is NOT relaxed and still blocks.
- Preserve `test_app_filing_source_kind_is_not_official_evidence` verbatim (the `app_filing`-non-official data invariant).

## Outcome

Landed in commit `84add274d`. `test_local_cross_period_carry.py` 5/5 green; real-behaviour, no mocks/skips/xfail.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
