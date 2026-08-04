---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:441894c60f3d32f30e6aa4de09b72f078f9b1e80caeacdb54112093f0cb4471c'
step_id: 'S83'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add a declaration-time guard refusing any StorageLocation carrying both override_policy=FIXED and a non-null settings_field, with a positive control proving an OPERATOR_OVERRIDABLE member with a settings_field is not flagged, because S18's existing gate only asserts that today's fixed members happen to carry no settings_field rather than refusing the combination itself, so the guarantee behind R10's keystore-must-not-relocate-out-from-under-its-bucket invariant is currently held by the absence of a field on today's declarations, not by a guard, and would silently stop being true the moment anyone gives a FIXED member a settings_field, which the model permits and which the existing gate would still pass because it would then be asserting a fact that had quietly stopped holding for the thing it names

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Add a second `model_validator(mode="after")` on `StorageLocation` refusing
  `override_policy=FIXED` combined with a non-null `settings_field`.
- Add a mutation-proof test exercising three cases: the violating declaration
  raises `ValidationError` at construction; the identical `settings_field` on
  an `OPERATOR_OVERRIDABLE` member (positive control) is unproblematic;
  removing only the `settings_field` from the `FIXED` declaration restores a
  legal construction.
- Confirm every one of the 57 real taxonomy declarations still constructs
  cleanly under the new guard.

## Outcome

The existing gate (`test_bucket_and_keystore_layout_is_fixed_not_operator_
overridable`) only asserted that today's `FIXED` members happen to carry no
`settings_field` — a fact about current declarations, not a constraint on a
future one. The new validator makes the contradictory combination
unconstructable at declaration time instead of merely absent so far.

Mutation-proven from the violating-declaration side (not by disabling the
guard): a `StorageLocation` built with `FIXED` and a `settings_field` raises
immediately; the guard does not misfire on a legitimate `OPERATOR_OVERRIDABLE`
member carrying the same field name.

## Notes

None. No skipped work, no scaffolds left in code.
