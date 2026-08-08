---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c9c453d5a865d082f7e20420b327d2d6e77914ba635fd5a7323e64580cf8ce5e'
step_id: 'S22'
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
     The S22 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The add the found-more-than-expected advisory emitting an INFO Notice for every period whose raw register count exceeds one, naming the modelo, period, winning expediente_id and superseded filing count, degrading gracefully to count-only wording when tipo_solicitud is absent from source metadata, verified by a test asserting INFO severity, never WARNING, and asserting the notice composes with rather than duplicates the re-capture divergence diff and ## Scope

- `src/cadrumo/application/live/_filed_data_capture.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the found-more-than-expected advisory emitting an INFO Notice for every period whose raw register count exceeds one, naming the modelo, period, winning expediente_id and superseded filing count, degrading gracefully to count-only wording when tipo_solicitud is absent from source metadata, verified by a test asserting INFO severity, never WARNING, and asserting the notice composes with rather than duplicates the re-capture divergence diff

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `found_more_than_expected_notices`, one INFO per period the register held more than one filing for.

## Outcome

INFO rather than WARNING, and that is the whole judgement. Several filings for
one period is the NORMAL shape of a corrected return — AEAT itself permits a
complementaria — so the operator is being told what their own history looks like,
not that something is wrong. Warning here would put a red flag on lawful
behaviour.

Composes with the re-capture divergence diff rather than duplicating it. They
answer different questions: this one says the register held more filings than were
kept for a period, the diff says a kept VALUE changed between two captures. A
period can trigger either, both or neither, so neither is derived from the other.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_onboarding.py -q -n0
    19 passed in 5.01s

One test asserts the severity is INFO and explicitly `is not` WARNING, because the
instinct to warn on a duplicate is exactly what this row rules against. Another
fires both advisories over one run and asserts the missing-filing warning stays
silent, proving they compose rather than one implying the other.

## Notes

Degrades to count-only wording when no winning expediente is known, rather than
printing a placeholder identifier as though it were AEAT's.
