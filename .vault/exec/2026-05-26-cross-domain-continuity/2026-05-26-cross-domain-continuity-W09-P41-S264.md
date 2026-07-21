---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S264'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-W08-B remove redundant _activate_subcommand_output_language wrapper in src/aeat/entrypoints/cli/_config/__init__.py

## Scope

- `it is now a one-line shim around the shared helper after the W08.P36 promotion landed`
- `collapse to direct calls`
- `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

- Reconciles the checked historical S264 row against the direct evidence named in the related reconciliation audit.
- Adds no production-source change.

## Outcome

- Restores the one-Step/one-record traceability edge for this historical checked row.
- The related audit names the exact supporting audit, execution record, or commit evidence.

## Notes

- This record asserts no new implementation or re-run verification; it records evidence reconciliation only.
