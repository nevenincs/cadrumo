---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S05'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P01.S05

Step `P01.S05` - Remove doclink mapping residue and preserve evidence-link audit binding.

## Description

Removed the remaining doclink kind mapping dictionary and confirmed there is no `add_link_attachment` import. Kept the `attach_manual_transaction_evidence` call site so the fetched attachment still records the existing transaction evidence provenance and bucket events.

## Outcome

Doclink now uses the same post-store linkage path as existing secure attachments.

## Notes

This step intentionally did not change the ledger evidence cross-reference call path.
