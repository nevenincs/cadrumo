---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:91ae7352eeef016fd39821d7d2110767e54bfb540dd9f3bd93e8cc38077ccd24'
step_id: 'S33'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype every classified bucket_event_id/event_id pydantic model field onto the existing BucketEventId alias at the sites not already using it

## Scope

- `src/cadrumo/application/modelo/_reconciliation_records.py`

## Description

- Re-read the row's target sites against the tree to establish whether the retype was still outstanding.

## Outcome

**No change was required. This row was already satisfied at the tree when it was read.**

Both model fields the row names already carry the `BucketEventId` alias, imported from the buckets domain facade. The alias itself is declared from the canonical hex-64 primitive, so the sites are enrolled exactly as the row intends.

The wider surface is in the same state: every consumer of this alias across the CLI payload modules and the bucket event model itself already uses it. No bare-`str` `bucket_event_id` or `event_id` model field remains at the sites this row covers.

## Notes

**Closed on a re-read, not on an edit, and the distinction is recorded rather than smoothed over.** An unchecked row is not evidence the work is undone: this campaign's tree takes heavy concurrent traffic and rows land from several directions. Marking it complete without this record would have made three different states wear one checkbox — delivered as specified, delivered narrower, and already-true-before-the-row-ran. This one is the third.

**Three sibling rows were NOT closed alongside it, deliberately.** Two of them had only their re-read precondition satisfied while their actions also require an edit that belongs to a deferred relocation, and a third sits inside a Phase escalated to the operator. All three were proposed for closure at one point and refused, because checking them would have recorded work that did not happen.
