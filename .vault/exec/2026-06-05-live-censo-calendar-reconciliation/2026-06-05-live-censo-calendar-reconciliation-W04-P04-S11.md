---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S11'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace live-censo-calendar-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-05-live-censo-calendar-reconciliation-plan placeholders are machine-filled by
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
     The Prove the active profile calendar contains legal obligation rows reconciled with live submitted and justificante-verified evidence and ## Scope

- `src/aeat/entrypoints/cli/_overview.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the active profile calendar contains legal obligation rows reconciled with live submitted and justificante-verified evidence

## Scope

- `src/aeat/entrypoints/cli/_overview.py`

## Description

Projected the active `me` profile calendar for 2026 under the same
authenticated live session used for the S10 read sweep (2026-07-10), in both
strict and `--allow-incomplete` modes.

- `app overview calendar --from 2026-01-01 --to 2026-12-31` (strict).
- `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`.

## Outcome

The calendar reconciles honestly against the live-read evidence gathered in S10
(which is empty for this account) and refuses to fabricate submitted or
justificante-verified state:

- Strict mode REFUSES with `REFUSED_CLI_BOUNDARY`: unresolved profile checks
  `censo.enrolment_unverified` and `irpf.estimation_regime`. It does not silently
  treat profile-derived obligations as live-reconciled censo obligations.
- `--allow-incomplete` returns the provisional projection: 10 obligation entries
  across modelos `100`, `130`, `303`, `390` with concrete filing dates,
  `taxpayer_model_declared=true`, and `completeness.computable_modelos =
  ['100','130','303','390']`.
- Warnings carry the live-reconciliation gap explicitly:
  `censo.enrolment_unverified` (affected modelos `100/130/303/390`, fix
  `aeat config profile censo pull && aeat config profile censo apply`) and
  `irpf.estimation_regime` (affected modelo `131`).
- No AEAT filing evidence, no verified justificantes, and 0 message events —
  consistent with the empty live account read in S10. The calendar shows
  local ready-to-file obligation rows without upgrading any to
  AEAT-submitted or justificante-verified state.

This proves the S11 contract in its enforceable direction: the calendar
distinguishes local filing readiness from AEAT-submitted / justificante-verified
state, and refuses to assert live reconciliation when the censo enrolment is
unverified and no official evidence exists. Positive submitted/justificante-
verified calendar rows cannot be shown because the authenticated account holds
no filed 2026 declaration and censo enrolment is blocked by the G313 launcher
defect (see S10).

## Notes

Positive live-submitted/justificante-verified calendar evidence is deferred to
the follow-up reference `2026-07-10-live-censo-calendar-reconciliation-reference`:
it becomes producible once the G313 censo launcher is re-grounded and the AEAT
account carries a filed declaration to reconcile against. No production code was
changed by this step; it is a live-verification proof over the already-landed
calendar hardening (W05 P05).
