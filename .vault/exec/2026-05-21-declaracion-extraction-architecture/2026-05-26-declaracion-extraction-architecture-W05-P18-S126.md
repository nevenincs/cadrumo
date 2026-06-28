---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P18.S126'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
---

# W05.P18.S126 - no-synthetic-Sede ADR

Accepted the no-synthetic-Sede live-surface ADR after the operator confirmed
that no synthetic data may be sent to Sede.

## Decision

Synthetic data is prohibited on AEAT-hosted live surfaces. Any registry
cross-reference whose `allowed_hosts` include an AEAT-owned host must advertise
`synthetic_data_allowed = false`.

The decision supersedes the previous allowance in the live-parity taxonomy for
Modelo 100 Renta WEB Open and Modelo 349 GROI/IXVI live synthetic inputs.

## Implementation Backlog

`W05.P18.S124` remains open until the follow-up implementation plan lands and
the registry, remote-state guard, and tests are changed.
