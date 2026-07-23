---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S08'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Implement the review projection (per-question status glyph set, jump targets, submit eligibility requiring all required valid and zero stale) and the deferred-status surfacing and ## Scope

- `src/cadrumo/application/flows/_review.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the review projection (per-question status glyph set, jump targets, submit eligibility requiring all required valid and zero stale) and the deferred-status surfacing

## Scope

- `src/cadrumo/application/flows/_review.py`

## Description

- Implement the review projection (per-page status rows, stale-orphan listing, flow-scope validator run, typed blocking verdicts, submit eligibility) and the assert_submit_eligible gate.
- Land in commit 91c5e51afc.

## Outcome

Submission is possible only from review with zero blocking verdicts; refusals enumerate every remaining item.

## Notes

Stale orphans of no-longer-visible pages stay listed so entered data never disappears from the summary.
