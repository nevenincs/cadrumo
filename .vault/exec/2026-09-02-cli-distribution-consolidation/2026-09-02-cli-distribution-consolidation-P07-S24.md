---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5113d53589a7d8216033fd26ebad655e0bfbf7ff46f3b8362a8c0ca2f2484c61'
step_id: 'S24'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Remove the tier rule, availability states and claim derivation

## Scope

- `dev/docs/download_matrix.py`

## Changes

M dev/docs/download_matrix.py
M dev/docs/tests/test_download_matrix.py
M dev/docs/tests/test_distribution_claims.py

## Notes

Both enums, the tier rule, the product-property model, its cross-check validator, the
claim derivation and the availability note are removed. Rendering no longer withholds a
channel's commands.

The unevidenced-claims gate is scoped to hand-authored prose rather than retired. A
generated zone is derived from the inventory, and every channel in the inventory owes
its rows before a release publishes - the readiness gate holds that half. Prose that
advertises a channel by hand still needs evidence already on disk, which is the half
this gate holds, and it is the half with teeth.
