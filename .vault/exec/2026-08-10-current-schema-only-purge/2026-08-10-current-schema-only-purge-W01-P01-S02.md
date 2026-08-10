---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0d89f16207f358b3412ef8cb9dc4219e5a69c167794f6998dee5319eae833051'
step_id: 'S02'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Stamp newly created profile records explicitly with the canonical schema version

## Scope

- `src/cadrumo/application/user_profile/_lifecycle.py`

## Description

- Verify the creation path against HEAD before writing anything.
- Confirm it is the sole production construction site for the live aggregate.
- Take no code change: the row was already satisfied.

## Outcome

No commit. The row asked for behaviour the tree already had before this campaign
began. The profile creation service constructs the record passing both the schema
id and the schema version explicitly from the loaded schema the validator holds,
at `src/cadrumo/application/user_profile/_lifecycle.py` lines 148 to 150. It is
the only production creation path; the immutable snapshot copies the record's
values rather than sourcing its own.

Reported as satisfied with the locator as evidence rather than manufacturing a
commit to close a checkbox. A row marked complete by a no-op change is
indistinguishable afterwards from one that was implemented, which is the exact
ambiguity the execution record exists to prevent.

## Notes

The row reads as open work in the plan and is not. Worth recording as a caution
about the plan's own accuracy rather than only about this step: an unchecked row
is not evidence the work is undone, and this campaign found the reverse case on
its first phase.
