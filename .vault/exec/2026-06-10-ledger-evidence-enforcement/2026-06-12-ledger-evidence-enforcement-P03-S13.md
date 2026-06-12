---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S13'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P03.S13

Step `P03.S13` - Add anti-tautology blob mutation proof.

## Description

Confirmed the roundtrip module mutates the persisted encrypted blob payload by swapping in a different valid ciphertext from the same bucket, then verifies that `AttachmentStore.verify_blob` raises on digest drift.

## Outcome

The regression test proves stored bytes are re-hashed and compared to the manifest id instead of trusting the manifest alone.

## Notes

The test mutates persisted storage state after a real successful store and does not reimplement the production hash logic.
