---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S57'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add registry-validation check that every bracket_table parameter brackets cover the revision declared date range

## Scope

- `src/aeat/domain/calculations/registry/_validate_revision_rules.py`

## Description

- Reconciled the bracket-table temporal validation to the Wave-3 evidence audit.
- Confirmed `6d9a17d3a` supplied the reviewed validation change.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

Historical evidence predates the current per-step record convention.
