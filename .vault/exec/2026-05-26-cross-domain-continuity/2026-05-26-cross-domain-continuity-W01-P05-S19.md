---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:c4116730249cc299a8bcb03875ad3508e97941c0315594a75cec82253fb9e119'
step_id: 'S19'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# preserve typed ProfileFactValue through _profile_fact_index instead of stringifying at the index entry

## Scope

- `update _resolve_one and _decimal_value to accept object and route via isinstance(value`
- `bool) before Decimal parse`
- `engine-facing ProfileSourcedBindingResult fields unchanged`
- `add guard at enum routing site to reject bool-typed values as enum dispatch keys`
- `src/aeat/application/modelo/_profile_binding.py`

## Description

- Reconciled the typed profile-value preservation change to the Wave-1 commit review.
- Confirmed `805008c5c` supplied the reviewed implementation and guard.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S20; each row receives its own record.
