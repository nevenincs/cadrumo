---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0c6c8a0f98f042570255a601c7f81aff19ff3f55b23c774c21650bbe361d7070'
step_id: 'S19'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype the bare-`str` CSV field onto `AeatCsv`

## Scope

- `src/cadrumo/adapters/inbound/borrador/_schema.py`

## Description

This row was DELIVERED BEFORE THIS RECORD EXISTED. The record is reconstructed
from the history.

`efd01cdf43` carried it, in the same commit and the same index as the sibling
reference-model retype. The inbound observation model's `csv` field moved from a
bare optional `str` with no bound at all onto the canonical alias, keeping its
optionality and its default. The commit added the alias import in the same hunk.

The field was the weakest of the CSV declarations this Phase set out to
reconcile: not a wider bound competing with the canonical one, but no constraint
whatsoever, on a value lifted out of a parsed borrador PDF.

## Outcome

Delivered, and the delivery matches the row. The field now carries the canonical
alias, still optional and still defaulting to absent, which is correct - a
borrador is a draft and may legitimately carry no CSV. Optionality is not a bound
this row was asked to remove.

Two divergences from the row as written, both in packaging rather than content.

First, the same packaging problem as its sibling: `efd01cdf43` is titled for the
deletion of unrelated forwarding aliases, and the CSV retype is an unannounced
passenger inside a roughly forty-file commit. The subject gives a reader no route
to this row.

Second, the row is scoped to one file, and this is genuinely a one-file change,
so the row's own boundary is honest. What the row could not anticipate is that
the delivering commit was not scoped to that boundary at all.

## Notes

The model has been edited since by unrelated work - the source-PDF digest field
now carries a content-digest alias it did not carry at the delivering commit.
That belongs to another row's surface and does not bear on this one.

No test in this row's scope was added or changed by the delivering commit. This
row asked only for a retype and the plan places the CSV shape regression on a
separate row, so the absence is not a gap in this row; it is a dependency on a
row that remains open.
