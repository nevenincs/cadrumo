---
step_id: S33
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P10.S33 — ProfileFactValue canonical collapse (BLOCKED)

## Status

**BLOCKED.** The two `ProfileFactValue` declarations are not semantically equivalent and cannot be consolidated without breaking persisted profile records.

## Evidence

- `domain/calculations/registry/_schema.py:944`: `ProfileFactValue = bool | int | str` (3-member union, no Decimal, no date, no None)
- `domain/user_profile/_values.py:48`: `type ProfileFactValue = str | bool | int | Decimal | date | None` (6-member union)

The registry schema's `ProfileFactValue` is used for formula binding inputs (limited to primitive JSON-serializable types the formula engine accepts). The user_profile `ProfileFactValue` is used for `UserProfileFact.value` which must accept `Decimal` (monetary amounts), `date` (e.g. birth dates), and `None` (unset facts).

Deleting the user_profile version and switching `UserProfileFact.value` to `bool | int | str` would:
1. Break existing persisted profile records that contain `Decimal` or `date` values.
2. Erase the `_coerce_profile_fact_value()` validator's ability to reconstruct Decimal/date from JSON strings.
3. Cause silent data loss on profile roundtrip through the persistence boundary.

The action tracker's "same name, different definition" classification is correct, but the ADR's resolution to use the registry canonical is semantically incorrect for the user_profile use case.

## Recommended resolution

Rename the user_profile version to `UserProfileFactValue` (distinct from the registry's `ProfileFactValue`) to eliminate the name collision without merging incompatible types. This is RENAME, not MERGE. Deferred to a follow-up plan.

## Files touched

None.
