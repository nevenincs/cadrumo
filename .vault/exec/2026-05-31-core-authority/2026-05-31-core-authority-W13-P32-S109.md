---
step_id: S109
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P32.S109 step record

## Step

Amend the core-authority ADR Consequences to mark MERGE-013 (IVA mapping) as wontfix
with rationale: 3-entry percentage-lookup and 5-entry VAT-classification mappings are
intentionally different in structure and domain semantics.

## Amendment

The MERGE-013 Consequences entry was updated (in the S107 ADR commit) to read:

> MERGE-013: WONTFIX. The 3-entry percentage-lookup mapping in domain/iva/_rate.py
> and the 5-entry VAT-classification mapping are intentionally different: they serve
> different domain operations (rate lookup vs classification) and the 2-entry difference
> reflects different legal categories, not a data gap.

This closes the audit finding AUDITPIPE-008 for the IVA false-positive case.

## Files touched

- `.vault/adr/2026-05-31-core-authority-adr.md` (amendment landed in S107 commit)

## Step Record note

The ADR amendment was included in the S107 commit to keep all three ADR changes atomic.
This step record documents the IVA-specific wontfix adjudication as a separate closure.
