---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S16'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Build the review screen with per-question status glyphs, jump-to-edit, and the submit gate wired to the engine's review projection

## Scope

- `src/cadrumo/adapters/inbound/tui/_review_screen.py`

## Description

- Build the review screen from the engine's review projection: per-question status glyphs, jump-to-edit targets, and a submit gate requiring all required valid and zero stale.
- Add clickable navigation over a data-review table and a section-grouped summary.
- Landed in `b38a036bae`, with clickable navigation and the data-review table in `9301091766` and the section-grouped summary in `9803d782ec`.

## Outcome

The review screen surfaces every question's status, lets the operator click or jump to re-edit, and blocks submit until the engine's review projection reports eligibility.

## Notes

None.
