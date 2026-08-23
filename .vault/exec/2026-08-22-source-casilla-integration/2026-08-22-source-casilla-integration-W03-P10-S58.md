---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6ab89bcac6597abe8fc9f5117718b3473737c86de99978768c08709b834c11e2'
step_id: 'S58'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
---

# determine whether finca amortization shares or requires a distinct source contract

## Scope

- `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`

## Description

- Separate rental-property amortization from activity-asset amortization.
- Preserve the finca property-year grain and its construction-basis, rental-day, rate, and cap rules.
- Assign finca amortization to its distinct casilla 0131 connection.
- Refuse reuse of activity material/intangible selectors or ownership.

## Outcome

The accepted ADR establishes finca amortization as a distinct source contract delivered with the finca slice. It cannot be folded into the activity-asset 0208/0227 authority.

## Notes

The broader finca aggregation implementation remains scheduled after the dedicated amortization slice.
