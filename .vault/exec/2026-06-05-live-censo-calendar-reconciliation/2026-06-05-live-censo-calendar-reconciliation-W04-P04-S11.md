---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:155ee1d9868d91584a47d824df1e558ec2301d68a3376098ce305d085370749d'
step_id: 'S11'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

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

The operator — the only party able to run the live account — accepted the
calendar's correct-refusal / no-fabrication behaviour as the S11 evidence and
confirmed the empty 2026 account is genuine (they have never filed the modelo),
so the zero-row live reads are the real expected state, not a defect. On that
acceptance this step is closed. Positive live-submitted/justificante-verified
projection remains producible in future once the G313 censo launcher is
re-grounded and the account carries a filed declaration (follow-up reference
`2026-07-10-live-censo-calendar-reconciliation-reference`, Blocker 1). No
production code was changed by this step; it is a live-verification proof over
the already-landed calendar hardening (W05 P05).
