---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S17'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Cover full-screen navigation, live validation, and review-submit scenarios headlessly with the Textual Pilot driver

## Scope

- `src/cadrumo/adapters/inbound/tui/tests/`

## Description

- Drive the full-screen frontend headlessly with the Textual Pilot driver across navigation, live validation, and review-submit scenarios.
- Cover multi-select, secret masking, save-and-exit, stale-orphan reset, select-revisit, and locale rebuild.
- Landed across `2b2c93bf90`, `9803d782ec`, and `4d4be90578`.

## Outcome

The full-screen frontend has real-behavior Pilot coverage of the complete navigation surface with no mocks, including the staleness and secret-masking edge cases surfaced in review.

## Notes

None.
