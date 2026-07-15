---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S157'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# extract shared currency-not-EUR guard to _shared_issue_reasons.py or sibling helper remove duplicates

## Scope

- `src/aeat/application/aggregation/`

## Description

- Reconciled this checked historical row against the direct evidence listed in the related reconciliation audit.
- Added this per-step record without changing production sources.

## Outcome

The retained evidence supports the historical check. This record restores the one-Step, one-record traceability edge.

## Notes

The related reconciliation audit names the exact historical commit or retained execution evidence for this row.
