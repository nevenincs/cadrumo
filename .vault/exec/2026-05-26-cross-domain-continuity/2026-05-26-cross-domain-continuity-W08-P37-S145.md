---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S145'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# remove build_error_envelope and json_output_requested from _errors.py __all__ update any importer to import from source module

## Scope

- `src/aeat/entrypoints/cli/_errors.py`

## Description

- Reconciled the redundant error re-export retirement to the Wave-8 evidence audit.
- Confirmed `882d6c027` supplied the reviewed change.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

Historical evidence predates the current per-step record convention.
