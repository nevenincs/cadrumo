---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:0bf1364a0be2e2505642f7af9f92936054119461115c951a482eadeda5e8b78f'
step_id: 'S11'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P03.S11

Step `P03.S11` - Add secure-storage regression gate for link-only manifests.

## Description

Added enforcement that rejects the link-only MIME sentinel in `Attachment` validation and in `AttachmentStore.write_manifest`. Extended `test_attachment_store_no_uri_list.py` to prove normal model validation and a tampered manifest write are both refused over a real SQLite-backed store.

## Outcome

No attachment manifest can be written through the secure attachment store as link-only evidence.

## Notes

Focused attachment and full attachment package tests pass.
