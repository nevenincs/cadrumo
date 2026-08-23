---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:077ec9aaed5a3b525000882cdf7978fe9cb970d5af61f1f90174652e1256547b'
step_id: 'S157'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# verify every reviewed capability locator remains re-fetchable and corresponds to its stable capability identity

## Scope

- `dev/source_connectivity/check.py`

## Description

- Derive the current evidence locator for every stable discovered capability identity.
- Require every reviewed locator path and optional line to remain re-fetchable.
- Require every explicit capability ID to retain correspondence with its detector-derived locator.
- Prove missing lines and valid-but-wrong locator drift fail independently.

## Outcome

Capability locators are now checked as mutable review evidence without becoming stable identity. All current
locators re-fetch and correspond to their explicit capabilities; a deleted line target or a locator moved
to another capability fails the monotonic gate.

## Notes

Ruff passed, the live locator check passed, and two mutation-shaped locator tests passed sequentially.
