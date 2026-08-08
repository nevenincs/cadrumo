---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c8f2fe033cb29a00c89bd91596273ccb0db07be4dc8371ffaa67e6687d76b99c'
step_id: 'S102'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Outcome

Closed as **already delivered by a peer**, not by this row's dispatch. The LIVA
art. 94 extraction sidecar was regenerated on 2026-08-07 by commit `0fccd9c5c4`,
*"fix(legal): regenerate the art. 94 extracted sidecar the validator actually
reads"*. The row stayed open afterwards.

## Verified at HEAD

Digest reconciliation against the payload beside it:

    declared: 0104bf5dff650c3ab16c5d1eadd12e8e4aa0b7ba0c67d76fd5d890aebccad067
    actual  : 0104bf5dff650c3ab16c5d1eadd12e8e4aa0b7ba0c67d76fd5d890aebccad067
    MATCH   : True

The digest match alone does not prove the `required_text` phrases resolve, so the
gates were run rather than inferred from it:

    pytest test_corpus_round_trip_gate.py test_corpus_catalogue_companion.py -n0
    18 passed in 9.25s

The row's stated blast radius — ninety-seven failures and eight errors from one
cause — is no longer reproducible at HEAD.

## Why the row outlived the fix

The commit subject names the artefact and the cause precisely, so this was
discoverable at any point by `git log` on the sidecar path. Nobody ran it,
because the row read as open and the plan is the thing consulted.

That is the standing hazard in this campaign: rows are swept asynchronously by
many concurrent agents, so an unchecked box means *"in flight, already built, or
unstarted"* and cannot distinguish them. The check is `git log -- <target path>`
before acting on a row, never the checkbox.

## The instrument note that belongs with this

The suite run first used to answer this question was backgrounded at its timeout
and its captured output ended mid-progress, with no summary line. It showed
several hundred passing dots and no failures, which reads as a green result. It
was not cited, because a truncated capture cannot distinguish "passed" from "was
still running" — the same class of error as reading a `| head`-truncated grep as
a complete list. The targeted gate run above replaced it.
