---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S12'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P03.S12

Step `P03.S12` - Add fetch-and-encrypt roundtrip coverage.

## Description

Confirmed `test_document_link_resolve_roundtrip.py` resolves a Drive link through the transport seam only, stores the returned bytes through a real `AttachmentStore`, reloads the manifest, and checks bytes, digest, MIME type, source reference, and blob verification.

## Outcome

The doclink byte-custody path has real storage roundtrip coverage.

## Notes

No storage fake, manifest fake, or repository monkeypatch is used.
