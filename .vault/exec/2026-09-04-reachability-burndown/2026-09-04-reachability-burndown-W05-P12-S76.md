---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:2e7d0c6ba94bf5fd83548d3d58ec0b8fdc857316296e671466e957d5c8d7d208'
step_id: 'S76'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Fix the defect this campaign created: the workflow gate stamped the approval basis against a transient empty transaction catalogue while the review queue recomputes it from whatever the bucket holds, so once drafts were persisted and the verdict recomputed, every stored draft in a bucket with a ledger read as an aged-out approval the first time anyone opened the queue. Approve against the bucket's own catalogue, which the approval consumes as a fingerprint and nothing else, and prove it with a case that seeds a bucket transaction first, since against an empty ledger the two digests agree by accident.

## Scope

- `src/cadrumo/application/modelo/workflow_gate.py`
- `src/cadrumo/application/modelo/tests/test_file_flow_draft_persistence.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/modelo/workflow_gate.py`
- `M` `src/cadrumo/application/modelo/tests/test_file_flow_draft_persistence.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` reverting the fix reproduces
  `TRANSACTION_CATALOGUE_CHANGED` on a freshly approved draft; with it, no reasons
- `verify:` `pytest .../test_file_flow_draft_persistence.py
  .../test_adapters_approval_staleness.py` 8 passed
- `verify:` `ruff check` and `ty check` clean
- `verify:` ledger validated -- 117 clusters, 274 symbols, no double classification

## Notes

This is a defect the campaign CREATED, and neither step that built it was wrong
on its own. Persisting the approved draft gave the staleness lifecycle a
subject. Recomputing the verdict in the review queue made the aged-out row
reachable. Together they compared a digest stamped over a transient empty
transaction catalogue against one recomputed from the bucket's real contents,
which disagree by construction wherever a ledger exists. Every stored draft
would have carried a permanent high-severity row that is always wrong.

The catalogue reaches approval as a fingerprint and nothing else, so approving
against the bucket's own catalogue does not give the calculation revision's
evidence a second owner. It makes the recorded digest mean what the refresh
already assumed it meant.

The first version of the test passed against the broken code. Its bucket had no
transactions, so the digest of a transient empty catalogue and the digest of the
bucket's own agreed by accident and the assertion held however the basis was
stamped. Seeding one transaction is what gave it teeth. An earlier draft of the
same test asserted through `drafts_pending`, whose empty result is the CORRECT
answer for a healthy approved draft and therefore cannot distinguish a working
invariant from a queue that saw nothing.

Two failures in `test_file_flow_verify.py` reproduce identically against
`git show HEAD:` of the gate and are unrelated: a modelo 180 revision lookup for
a year the registry does not declare, and a locale-key assertion.
