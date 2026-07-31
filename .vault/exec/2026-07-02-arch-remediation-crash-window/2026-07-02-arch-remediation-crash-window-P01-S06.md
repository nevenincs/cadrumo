---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:93366e808acaa82aaff8b9257fd7dbc1fe17280de0b5c2ac4330839fb085add6'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Confirm the attachment-and-evidence-put ordering at HEAD and resolve the orphan-blob-GC-sweep-exists-or-declared-non-goal cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the attachment/evidence-put ordering at HEAD; recorded that the attachment store writes both the content-addressed blob and its manifest as separate rows in the same encrypted SQLite secure-object store. Resolved the orphan-blob-GC-sweep cell in the reference body.

## Outcome

Confirmed guarantee: an orphan blob is content-addressed, unreferenced, and idempotent-dedup on retry; a GC sweep resolved as a documented non-goal.

## Notes

The matrix `B (bytes) then S` two-substrate model was wrong for this store; both blob and manifest are SQLite secure-object rows.
