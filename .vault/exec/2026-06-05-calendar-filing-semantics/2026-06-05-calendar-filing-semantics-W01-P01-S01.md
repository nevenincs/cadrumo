---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S01'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W01.P01.S01`

Scope: add calendar filing-evidence models and pure evidence merge helpers.

## Description

- Add local filing and AEAT submission state enums.
- Add nested calendar filing evidence on deadline entries.
- Add pure evidence projection from local Modelo filing records, AEAT calendar events, and persisted justificante calculation observations.
- Add period alias matching so deadline periods such as `2025Q1` reconcile with AEAT periods such as `1T`.

## Outcome

Calendar entries can now carry local ready-to-file state separately from AEAT submitted, accepted, and justificante-verified state.

## Notes

The first implementation returned duplicate rows for alias keys; focused tests caught this and the helper now returns unique evidence rows while keeping aliases internal for lookup.
