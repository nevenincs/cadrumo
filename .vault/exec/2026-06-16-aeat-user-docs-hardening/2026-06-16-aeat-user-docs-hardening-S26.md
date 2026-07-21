---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S26'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden reconcile.md

## Scope

- `docs/how-to/reconcile.md`

## Description

- Verify-close: read `reconcile.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding m11 (mismatches showed SHA-256 hashes, not legible values; evidence_invalid framing): the page now documents the three verdicts (matches / mismatches / evidence_invalid), and a `mismatches` verdict names the differing header field and shows the LOCAL value next to the value in the justificante (legible, not a hash).
- Confirm the page states honestly that reconciliation compares header fields (modelo, filing year, period, tax id), not box/casilla totals, and points to the amendment path for a wrong box value.
- Confirm the two transports (`reconcile file --file` and `reconcile pull`) and their auth/refusal behaviour are documented.

## Outcome

- Page verified compliant at HEAD; finding m11 resolved (legible mismatch values; evidence_invalid as a documented verdict). Delta: none required.

## Notes

- Residual m16 (invalid-PDF parser-internals leak) is APP-side, fixed per the audit (clean typed `evidence_invalid` refusal). CLI conformance gate green.
