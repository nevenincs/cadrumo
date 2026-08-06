---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:72d2474e5aa38bc36cba07e7cde215e1a95d7e51da7f389ab9cbb126759ad7b6'
step_id: 'S40'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# update CLI consumer to import from canonical domain module or via thin application re-export

## Scope

- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Reconciled the canonical applicability-source collapse to the Wave-2 review.
- Confirmed `30065a92e` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-29 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S38, S39, S41, and S42; each row receives its own record.
