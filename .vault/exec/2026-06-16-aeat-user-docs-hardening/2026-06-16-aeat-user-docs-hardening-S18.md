---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden modelo-036.md

## Scope

- `docs/how-to/modelo-036.md`

## Description

- Verify-close: read `modelo-036.md` against its 2026-06-18-audit assessment and confirm resolution at HEAD.
- Confirm the audit's own positive verdict for this page: `modelo-036` is the cleanest command surface (Doc 4/5, App 5/5, 0 major). The alta/modificación/baja, list, view-by-id-and-prefix, no-match refusal, idempotency, and `--note-only` flows are all delivered exactly as documented, with graceful and instructive refusals.
- Confirm the record-a-036-you-filed-at-AEAT framing (the tool records the census declaration you filed; it never submits to AEAT) is stated.

## Outcome

- Page verified compliant at HEAD; the audit records `modelo-036` as clean with no major findings. Delta: none required. CLI conformance gate green.

## Notes

- The cleanest surface in the audit; verify-close confirms it holds at HEAD.
