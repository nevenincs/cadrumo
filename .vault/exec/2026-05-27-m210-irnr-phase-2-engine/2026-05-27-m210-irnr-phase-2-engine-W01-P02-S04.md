---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S04'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
  - "[[2026-07-09-m210-irnr-phase-2-engine-adr]]"
---

# add the M210 period token `0A` (agrupacion anual) to the canonical period grammar scoped to M210, resolved through the single `Period.contains` boundary authority

## Scope

- `src/aeat/domain/period.py`

## Description

- Verify-closed: the M210 agrupacion-anual period token `0A` is ALREADY present and wired at HEAD; no code edit was required or made.

## Outcome

- `0A` is `StandardPeriodCode.ANNUAL` in the canonical grammar (`core/_period.py`), fully resolved through the single `Period.contains` boundary authority (span 1 January-31 December), and covered by an existing helper test (`domain/tests/test_period.py`, `0A` -> 1 Jan-31 Dec). It is a SHARED annual token already used by ~10 modelos (M100, M156, M121, M189, ...), not M210-specific.
- No edit: scoping a shared token to a single modelo in the core grammar would be wrong (it would break the other annual modelos). Per-modelo period applicability is a registry `period_selector` concern, not a core-grammar edit.

## Notes

- The plan step's original scope (`src/aeat/domain/period.py`) named the boundary-helper module; the canonical grammar authority is `aeat.core.Period`. Both already carry `0A`. S04 is satisfied at HEAD with no change.
