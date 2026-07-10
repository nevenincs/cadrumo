---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S28'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden review-queue.md

## Scope

- `docs/how-to/review-queue.md`

## Description

- Verify-close: read `review-queue.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M18 (page promised JSON with legal_refs but offered none; unknown `--kind` gave a bare "value invalid"): JSON is now documented via the global `aeat --format json` flag placed before the command, and the page lists the accepted `--kind` tokens (`ledger_transaction`, `purchase_invoice_evidence`, `modelo_finding`, ...); the CLI now names the accepted set on a bad `--kind` (the instructive-gate fix per aeat-architecture-boundaries).
- Confirm finding m17 (`<profile-id>` placeholder literal in the Bucket cell) is resolved: the intentional paste-safety redaction is kept and the redundant column dropped.

## Outcome

- Page verified compliant at HEAD; findings M18 and m17 resolved (2026-06-19 documentation + app fixes). Delta: none required.

## Notes

- The global-JSON-flag position is the same S-DRIFT meta-finding fix shared with verification-reports (M8). CLI conformance gate green.
