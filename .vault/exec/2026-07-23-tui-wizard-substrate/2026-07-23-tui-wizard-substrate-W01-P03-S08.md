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
