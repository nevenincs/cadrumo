---
step_id: S107
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

# core-authority W13.P32.S107 step record

## Step

Amend the core-authority ADR Rule 7 Rationale to acknowledge that CalendarCCAA
is NOT a 100% geographic duplicate of CCAA, and add a wontfix Consequences entry
for MERGE-002.

## Amendment

Rule 7 Rationale section corrected: CalendarCCAA has incompatible value formats
(ISO 3166-1 alpha-2 codes vs lowercase Spanish names) and different member sets
(24 vs fewer). MERGE-002 consequence entry updated to WONTFIX status.
RELOC-021/RELOC-022 marked CANCELLED.

## Files touched

- `.vault/adr/2026-05-31-core-authority-adr.md`
