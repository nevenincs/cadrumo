---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S20'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C4-2 Delete the duplicate _display_decimal and import the canonical from _actions_common

## Scope

- `src/aeat/application/ledger/_review_projection.py`

## Description

- Re-verified the duplication at HEAD: the canonical `_display_decimal` lives in
  `_actions_common` (already imported by `_actions_manual`) and was re-declared
  byte-identically in `_review_projection`.
- Added `_display_decimal` to the existing `from ._actions_common import ...`
  line in `_review_projection` and deleted the local re-declaration.
- Removed the now-unused `from decimal import Decimal` import.

## Outcome

Committed as `2448865b1`, tagged `relocation:_display_decimal`. Lint clean,
ledger collect-only clean (298 tests), `test_actions_review.py` 5/5 green. No
public shape change; no peer WIP on the file at edit time.

## Notes

None. Single-file delete-local + import-canonical, behaviour-preserving.
