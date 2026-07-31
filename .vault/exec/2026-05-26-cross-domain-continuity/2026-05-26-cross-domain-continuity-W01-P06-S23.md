---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:442ac0c29b18cacbd7e3b429e8f45d52f78dc865be957782df999bc5505a9091'
step_id: 'S23'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add a paired comment at _CIF_KIND_LETTERS in _documents.py explaining the 17-char set is the AEAT current-spec closed catalogue and K L M are deliberately excluded as historical-only forms tolerated by the legacy path

## Scope

- `src/aeat/core/identity/_documents.py`

## Description

- Reconciled the CIF contract documentation work to the Wave-1 commit review.
- Confirmed `c55954263` supplied the reviewed change and pinning test.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S22 and S24; each row receives its own record.
