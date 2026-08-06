---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:706b964e9ab0e608decaf3a367d3eedde0c19a7d9e0609835ac3acf5f334efdc'
step_id: 'S22'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P06.S22`

Scope: `src/aeat/domain/usage_ratios/_service.py`.

## Description

- Added `frozenset[SpendingCategory]` to the home-office category helper.
- Added `dict[SpendingCategory, Decimal]` to the censo-derived ratio map.

## Outcome

The usage-ratio service no longer reports missing generic argument diagnostics
in the focused Pyright run.

## Notes

Usage-ratio behavior tests passed.
