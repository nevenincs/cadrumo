---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S03'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P01.S03

Step `P01.S03` - Rewire doclink to fetch bytes and persist secure attachment manifests.

## Description

Confirmed `ledger_doclink` calls `resolve_document_link`, then persists the returned bytes through `add_attachment_bytes` and `AttachmentStore`. The manifest records the original source and source reference as metadata while the attachment id and `sha256` come from the fetched bytes.

## Outcome

The doclink success path now stores encrypted document bytes under the attachment blob and manifest namespaces instead of storing a pointer.

## Notes

Roundtrip coverage in `test_document_link_resolve_roundtrip.py` validates fetched bytes, digest, MIME metadata, and manifest reload.
