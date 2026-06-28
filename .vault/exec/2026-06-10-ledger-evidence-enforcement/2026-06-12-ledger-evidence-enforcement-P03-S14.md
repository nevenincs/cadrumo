---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S14'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P03.S14

Step `P03.S14` - Add Gmail and URL refusal coverage.

## Description

Confirmed the document-link roundtrip module asserts Gmail and arbitrary URL references raise `OutboundStoragePermissionError` with the required scope in context and leave a real attachment store empty.

## Outcome

Unfetchable remote references cannot produce attachment manifests or blobs.

## Notes

The Drive out-of-scope refusal remains covered by the resolver-level tests.
