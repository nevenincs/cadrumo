---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:328c81350f6fef6e725e24d5cb17eec6b1ed3d476db92af7f673af383bae5f92'
step_id: 'S73'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the four writer-less categories the liveness gate found dormant with a stated reason each, status-cache for the never-wired AEAT status reader, storage-backup for archive and bundle export writing only where the operator directs, and inbox and inbox-pdf set only by fixtures

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare `dormant_reason` for the four categories the liveness gate found with no production consumer: status-cache (AEAT status reader never wired), storage-backup (archive/bundle export writes only where the operator directs), inbox, inbox-pdf (only ever set by fixtures).

## Outcome

Landed in commit `f7493b4431`. Deletion or wiring of these four categories is a separate, still-open decision (see S74). No vault record was found substantiating an earlier claim that three of them were "confirmed dead and pending deletion, blocked on file contention" — code at this reconciliation shows all four declared-dormant and untouched.

## Notes
