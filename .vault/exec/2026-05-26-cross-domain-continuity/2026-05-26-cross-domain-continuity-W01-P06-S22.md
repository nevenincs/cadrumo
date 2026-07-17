---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add a module-level cross-reference comment in _tax_id.py documenting that _CIF_LEADERS is a historical-tolerance superset of _documents._CIF_KIND_LETTERS K L M accepted only on the legacy NIF validator path not the IdentityDocument shape gate

## Scope

- `src/aeat/core/identity/_tax_id.py`

## Description

- Reconciled the CIF contract documentation work to the Wave-1 commit review.
- Confirmed `c55954263` supplied the reviewed change and pinning test.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S23 and S24; each row receives its own record.
