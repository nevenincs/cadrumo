---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S10'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Add application-to-adapters count ratchet

## Scope

- `src/aeat/tests/test_importlinter_ledger.py`

## Description

- Added a layered-contract count ratchet for application-to-adapters ignore edges.
- Added an explicit assertion that the blanket application wildcard is absent.
- Added a second ratchet for the source-module pins to keep the enumerated production baseline from growing.

## Outcome

The application-to-adapters baseline is 329 layered ignore edges. The source-module pin baseline is 77.

## Notes

The ratchet allows burn-down by deletion but fails growth unless an accepted decision loosens the gate.
