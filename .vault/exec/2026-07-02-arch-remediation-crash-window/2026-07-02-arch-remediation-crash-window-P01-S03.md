---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Confirm the hard-delete ordering at HEAD and resolve the partial-directory-detection-in-repair-integrity cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the hard-delete ordering at HEAD; recorded soft tombstone then trash-rename whole-directory removal, and the idempotent re-run plus readiness refusal plus scan-issue detection. Resolved the partial-directory-detection-in-repair-integrity cell in the reference body.

## Outcome

Confirmed guarantee: idempotent re-removal, non-ready health refusal, and torn-manifest partial-directory detection.

## Notes

A partial directory whose manifest is absent is excluded from the live inventory as reclaimable garbage, consistent with create-rollback staging semantics.
