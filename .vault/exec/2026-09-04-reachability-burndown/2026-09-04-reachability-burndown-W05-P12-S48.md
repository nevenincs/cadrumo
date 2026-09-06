---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:3ed9787ca282af311ed16c10df4e5af4906f8b49d1237b9d1de343bc1f78ead7'
step_id: 'S48'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate the recipient keypair accessors and the review-only workspace, using the module-surface split to separate a displaced accessor inside a working feature from a feature with nothing behind it: the encryption module is mostly live and its ensure path is documented to mint a keypair on first use, subsuming the plain loader; whereas the workspace opener and the guard refusing an official action are both unreached, and the type they produce has exactly one production consumer, the collaboration audit emitters this ledger already records as reached by nothing, so the type is held alive only by code that is itself dead and no guard refuses an official action inside a review-only workspace

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The review-only workspace joins the collaboration audit emitters recorded
earlier as one feature rather than two findings: no opener, no authority guard,
no audit trail, and the workspace type's only production consumer is those
unreached emitters. An official action inside a review-only workspace is
therefore refused by nothing.
