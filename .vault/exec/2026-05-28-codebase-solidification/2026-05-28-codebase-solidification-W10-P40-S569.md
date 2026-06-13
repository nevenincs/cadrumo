---
step_id: S569
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W10.P40.S569 — _VARCHAR_64 constant extraction

## Outcome

Added `_VARCHAR_64: Final[str] = "VARCHAR(64)"` at module level in
`src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
Added `Final` to the `typing` import.

Replaced all 10 callsites (5 in the column-definition tuple at lines
40-44, 5 in the quarantine DDL string at lines 261-265) with the
constant reference. The DDL sites use f-string interpolation (`f"  revision_id {_VARCHAR_64},"`)
which Python implicit-string-concatenation handles correctly.

## Grep post-condition

- Before: 10 bare `"VARCHAR(64)"` occurrences in `secure_objects.py`
- After: 1 (the constant's own definition)

## Commit

`5cc2fffd6`
