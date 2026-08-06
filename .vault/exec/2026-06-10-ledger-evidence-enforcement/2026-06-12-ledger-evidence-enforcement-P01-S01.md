---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:49e3da09d34f5cbd5b6da3e9301ad413de5120b89c1effe2bb35f7104d813a86'
step_id: 'S01'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P01.S01

Step `P01.S01` - Delete the link-only attachment service path.

## Description

Confirmed `add_link_attachment` is absent from `src/aeat/domain/attachments/_service.py` and absent from the package `__all__` surface. The retained service helpers are byte-bearing paths only.

## Outcome

The attachment service no longer exposes a function that can store a remote reference as evidence bytes.

## Notes

Verified by production grep for `add_link_attachment`, which returned no matches.
