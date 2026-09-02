---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:59aee56c5eb719c652d8471cb54976e710a57ceb159792061682cca91fc73be1'
step_id: 'S26'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Rename the sealed release record's channel field to drop the claim vocabulary

## Scope

- `dev/release/release_candidate.py`

## Changes

D dev/release/release_candidate.py

## Notes

No rename was needed. The sealed candidate record retired with the bespoke release
path, so the field naming the claimed channel set no longer exists to carry the
vocabulary.
