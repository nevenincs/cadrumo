---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:124f0ffd82d832ec4e0955a295548c15af5aa3ab35ce0ee1def2822d1492a282'
step_id: 'S61'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Publicise the preflight issue detail, whose canonical alias elides at five hundred and twelve where the payload rejects, so the two disagree about what an over-long detail should do

## Scope

- `src/cadrumo/application/ledger/preflight.py`

## Changes

- `verify:` `IssueDetail` is declared in `core/prose_elision.py` and consumed at three sites

## Notes

Closed by S129. The step describes the defect exactly: the canonical elides at
512 where the payload rejected, so the two disagreed about an over-long detail.

The canonical's own comment says why eliding is right -- refusing "would drop the
explanation for the exclusion AND fail the aggregation that produced it, a silent
under-declaration dressed as a validation error" -- and the payload reintroduced
that failure one layer out. A 600-character detail is now accepted and elided
where it was refused.
