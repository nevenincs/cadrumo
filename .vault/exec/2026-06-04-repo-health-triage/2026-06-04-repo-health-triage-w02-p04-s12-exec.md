---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S12'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P04.S12`

Scope: `src/aeat/application/aggregation/_counterpart.py`.

## Description

- Replaced local counterpart source-kind validation with the shared core
  counterpart source-kind helper.
- Kept bare `invoice` rejected at observation construction.

## Outcome

Counterpart observation construction now returns the narrowed enum-backed
counterpart source-kind type without local casts.

## Notes

No behavior relaxation was introduced.
