---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:993999f805f7e883b32965c2a4a32b83d83370d8f01013a8dcf9ef3b80eb1a1f'
step_id: 'S94'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on the two application/modelo edit-execution functions that compose a secure-object write without asserting a revision, a pre-existing finding the composing-write gate reports

## Scope

- `src/cadrumo/application/modelo/_edit_execution.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/profile/tests/test_every_composing_write_is_declared.py`
- `verify:` `pytest test_every_composing_write_is_declared.py -n 0 -m ""` -> pass (8), was 1 failing

## Notes

Ruled CLOSED rather than merely inventoried, which the gate's own docstring is
careful to distinguish: "It is an inventory, not a clearance. Being listed
records that a site writes a document without asserting a revision; it does not
certify the site is safe."

Both sites qualify under the first of the three situations that gate names --
the document was never read, so there is no revision to assert.
`_co_commit_receipt` CONSTRUCTS a `ModeloEditMutationResultReceiptV1` from the
request and writes it; nothing loads it first. `apply_modelo_edit` is its
enclosing function and that receipt is its only composing write, everything else
being delegated to the calculation boundary and the single-writer primitive.

The receipt is additionally per-record rather than a singleton catalogue: its id
is a content hash over the operation, baseline, calculation revision and bucket
event, so two writers can only collide by writing the identical receipt. That is
the narrowing the gate's third situation describes, and here it compounds with
the first rather than substituting for it.

Both entries say "closed, not merely unclassified", because this inventory
deliberately admits which of its rows have been judged and which have only been
recorded -- borrowing a neighbour's reason is the failure it warns about.
