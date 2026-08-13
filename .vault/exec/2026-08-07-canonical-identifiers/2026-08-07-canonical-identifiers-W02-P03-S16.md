---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1696b84d45d3ab6bba0a99c3f88e9ec17acac54e8eacffb914a969328859df79'
step_id: 'S16'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype `JustificanteRef.csv` onto `AeatCsv`, removing its now-redundant field validator

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`

## Description

This row was DELIVERED BEFORE THIS RECORD EXISTED. The record is reconstructed
from the history, and both halves of the row were checked against the tree
rather than inferred from the commit subject.

`efd01cdf43` carried it. In one hunk it retyped the reference model's `csv`
field from a bare `str` carrying an inline minimum and maximum length onto the
canonical alias, deleted the `_csv_shape` field validator that had been
re-checking the same contract through a module-local shape predicate, and
dropped the now-unused import of that predicate.

Both halves of the row therefore landed together, which matters: the field
validator was the second authority the row exists to remove. A retype that left
it standing would have moved the constraint without retiring the duplicate, and
the model would have carried one contract declared twice - once as an annotated
type and once as an imperative check raising a different error class.

## Outcome

Delivered in full, both halves. The field now reads as the bare canonical alias
with no inline bound, and the module carries no CSV shape validator and no
import of the predicate that backed it. The only remaining field validators on
that module are for unrelated fields.

The row's instruction and what shipped agree exactly. The divergence worth
recording is not in the content but in the packaging.

`efd01cdf43` is titled for the deletion of unrelated forwarding aliases and
touches roughly forty files under that heading. The CSV retype rode inside it as
an unannounced passenger. Nothing in the subject, and nothing in the plan,
connects that commit to this row - which is precisely why the row still read as
open with no record until it was reconstructed by pickaxe. A reader searching
the history for the CSV retype by subject will not find it.

## Notes

An earlier commit, `c272504f9d`, touched the same model and the same file three
hours before, retyping the sibling expediente field and deleting ITS two shape
validators, but left the `csv` field on its inline bound and left the `_csv_shape`
validator in place. Reading only that commit would give a false negative on this
row.

The predicate the deleted validator called still exists, canonically in the core
shape module, with three live consumers - the inbound receipt extractor, the
public verifier and the remote declarations reader. Only this model's use of it
was retired, and a follow-on commit removed the sede package's local re-export of
it so the three consumers now reach the core declaration directly. The remote
declarations reader's use is the subject of a separate row in this Phase, which
this one does not close.
