---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:cc87526a8751179b4ca6b787aa3472d485efd205b6b6a3ae42f0243e4479dedb'
step_id: 'S17'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden ledger-evidence.md

## Scope

- `docs/how-to/ledger-evidence.md`

## Description

- Verify-close: read `ledger-evidence.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M17 (`invoice add` -> `link --invoice-id` broken; `--attachment-id` source undocumented): the invoice catalogue-create flow was added so the linkable invoice path works end to end; the page now documents the `--attachment-id` limitation HONESTLY - no operator command currently surfaces the 64-character attachment id, so it directs the reader to `--purchase-invoice-evidence-id` or `doclink` instead until one does.
- Confirm the evidence-bytes-not-links invariant is documented: Drive doclink fetches and encrypts the bytes; Gmail links, arbitrary URLs, and out-of-scope Drive files are refused with an actionable message.

## Outcome

- Page verified compliant at HEAD; finding M17 resolved (catalogue-create landed 7208bb3f0; the residual attachment-id gap is documented honestly rather than papered over). Delta: none required.

## Notes

- The honest "no command surfaces the attachment id yet" note is the correct treatment of a real current-state limitation, not a doc defect. CLI conformance gate green.
