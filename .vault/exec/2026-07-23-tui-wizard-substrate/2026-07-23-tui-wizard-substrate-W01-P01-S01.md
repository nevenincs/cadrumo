---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S01'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Declare the substrate closed value sets (widget kinds including repeating-group and compare-select, page status including stale and deferred, flow mode, checkpoint availability) as StrEnums

## Scope

- `src/cadrumo/core/flows.py`

## Description

- Declare FlowWidgetKind (seven carried tokens plus compare_select), PageStatus (unanswered/answered/invalid/stale/deferred), FlowMode, CheckpointAvailability, CopyRefKind, and FlowIntentKind as core StrEnums with the DEFER_TOKEN and instance-separator constants.
- Land in commit 91c5e51afc.

## Outcome

Closed value sets live in core per the core-authority discipline; consumers route on members, never raw strings. Verified by the pinned enum suite (30e5884352) and ruff clean.

## Notes

FlowIntentKind is a forward contract for the full-screen frontend; flagged by review as unconsumed at this checkpoint (L1, accepted).
