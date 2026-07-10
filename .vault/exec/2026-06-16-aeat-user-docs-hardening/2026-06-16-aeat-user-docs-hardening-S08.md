---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S08'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden correct-ledger-entries.md

## Scope

- `docs/how-to/correct-ledger-entries.md`

## Description

- Verify-close: read `correct-ledger-entries.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M11 (`split` -> `merge` broken at the seam): the split verb now emits the child transaction ids that `merge --child-id` requires, so the documented undo path is completable; the page documents `ledger split` with `--child-amount`/`--child-description` and the merge-back path.
- Confirm the update / archive / stash lifecycle verbs and their active-transaction refusals are documented.

## Outcome

- Page verified compliant at HEAD; finding M11 resolved (split child-id emission fixed 2026-06-19; `_ledger_lifecycle_cli.py` + payload). Delta: none required.

## Notes

- Residual m12 (stash/archive print no lifecycle status) is an APP-side ergonomics finding, out of documentation scope. CLI conformance gate green.
