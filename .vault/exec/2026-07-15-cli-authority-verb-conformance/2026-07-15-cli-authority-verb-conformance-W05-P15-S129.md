---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:5afda44ae8cd47d524bccfb9a23c720411ed96ed041b47e97d7735bbe8ea8db0'
step_id: 'S129'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove evidence-link input and evidence-update output fields from ledger link

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`

## Description

- Read the ledger link result schema in the named payload module and enumerate its declared fields.
- Confirm no evidence-link input field and no evidence-update output field rides on the link result.

## Outcome

The link result declares only link metadata: an operation, a bucket id, a transaction id, an invoice id, and an actor. Its docstring states the separation outright, recording that link establishes an invoice-only bidirectional relationship and that evidence assignment is a separate operation which never rides on this result.

The evidence-update result class still imported by the module belongs to the separate and live evidence update verb, which is a different surface from the link result this Step governs.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
