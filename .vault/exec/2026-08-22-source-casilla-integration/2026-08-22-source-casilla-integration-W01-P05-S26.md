---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fa0751a5d0b56f7e88e6781943b855617d79815ca083e21c8b94692cdeee63d7'
step_id: 'S26'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# reject expired blocked rows and unresolved rows without an owner and bounded follow-up

## Scope

- `dev/source_connectivity/check.py`

## Description

- Define the unresolved disposition set explicitly from the canonical closed vocabulary.
- Reject unresolved rows without an owner and bounded follow-up ownership.
- Reject blocked rows whose review expiry has arrived without adjudication.
- Accept an explicit civil date for deterministic gate verification while defaulting the live check to today.

## Outcome

The monotonic gate now enforces time-bounded accountability in addition to capability coverage. Every
candidate and blocked row must retain an owned finite follow-up, and an expired blocker fails rather than
remaining indefinitely deferred. The census is current as of 2026-08-23.

## Notes

Ruff passed and the live gate completed with an explicitly supplied 2026-08-23 civil date.
