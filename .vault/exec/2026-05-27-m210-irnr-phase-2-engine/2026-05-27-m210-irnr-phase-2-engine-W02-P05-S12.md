---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:845dcda20ee0fac5cf0407ca40c0d95e1a20455881f897c1a0c819055445cdf9'
step_id: 'S12'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# Add secure-store behavioural tests proving ES-only M210 aggregation, retained provenance, and source-jurisdiction/classification mutation outcomes

## Scope

- `src/aeat/application/aggregation/tests`

## Description

- Exercise persisted transactions through the real secure store and filing-snapshot path.
- Verify ES-only admission, retained classification and source evidence, annual code-35 derived rows, and absence of manual `[5]` fact basis in ledger mode.
- Mutate source jurisdiction and classification facts after calculation and verify that the stored snapshot becomes stale.

## Outcome

The tests establish behavior at the secure persistence boundary rather than mirroring resolver logic. The focused M210 suite, including these secure-store cases, passes 86 tests. Landed in `8f5f690ed0`.

## Notes

No fakes, stubs, or monkeypatches were introduced.
