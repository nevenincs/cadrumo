---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S07'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Replace the application adapter wildcard

## Scope

- `.importlinter`

## Description

- Removed the blanket `aeat.application.** -> aeat.adapters.**` ignore entry.
- Added individually pinned application source-module edges from the enumerated 77-module baseline.
- Added exact application test-source adapter edges surfaced by Import Linter after the blanket wildcard was removed.

## Outcome

The layered contract now has 329 application-to-adapters ignore edges and no blanket application wildcard.

## Notes

The narrower `aeat.tests.secure_sql -> aeat.adapters.**` wildcard remains because `src/aeat/tests/secure_sql.py` is a shared secure-storage helper that imports real persistence adapters across multiple test surfaces.
