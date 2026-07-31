---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:4d774d1e97dee990920fcd51cb16207612468c16ad9d56552726d4285e99d6ba'
step_id: 'S09'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Cover complete navigation scenarios (back, jump, gating-answer change marks dependents stale, reset, restart, repeating-group instances, deferral) with engine transition tests

## Scope

- `src/cadrumo/application/flows/tests/test_engine.py`

## Description

- Author the engine transition suite covering navigation, canonicalisation, staleness, reset, restart, repeating groups, deferral, section-exit blocking, and the submit gate.
- Land in commit 30e5884352 (18 tests).

## Outcome

All 18 green; a real cross-field validator registered through the public registry exercises the section-exit gate.

## Notes

Authored by the dispatched high-executor.
