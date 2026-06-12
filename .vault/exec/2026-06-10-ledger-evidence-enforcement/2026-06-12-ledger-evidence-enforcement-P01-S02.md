---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S02'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P01.S02

Step `P01.S02` - Remove doclink-only kind mappings while retaining byte-bearing enum members.

## Description

Removed the `DocumentLinkSource` to `AttachmentKind` mapping dictionary from `ledger_doclink`. `AttachmentKind.EMAIL_MESSAGE`, `AttachmentKind.DRIVE_DOCUMENT`, and `AttachmentKind.OTHER` remain in the enum because they are still valid byte-bearing attachment kinds outside the deleted link-only path.

## Outcome

The doclink command no longer assigns Gmail or URL link-only artefact kinds; successful doclink storage is a fetched Drive document.

## Notes

No enum members were retired because their byte-bearing use remains valid.
