---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:2e286eea98c0081ac858f734592d4fa91c18610c43069bd8e6da5ba021650303'
step_id: 'S48'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
