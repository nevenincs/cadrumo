---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e785e0fc108135820344a5e8faf9fa22f471b1a6e4c5ac98768680f9da236209'
step_id: 'S29'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enroll the connectivity check in the repository quality-gate surface

## Scope

- `pyproject.toml`

## Description

- Enroll the source-connectivity test directory in pytest's canonical default testpaths.
- Confirm the repository lane-reachability model assigns every connectivity test to active unit and CI lanes.
- Run the complete discovery, census-completeness, and mutation ratchet suite through the enrolled path.

## Outcome

The ordinary repository unit gate now runs the source-connectivity census ratchet automatically. All 13
connectivity tests are named by active lanes and selected by their unit marker; none remains dependent on
a maintainer remembering the standalone comparison command.

## Notes

An explanatory comment placed inside the multiline `testpaths` array was initially consumed as path text
by the repository's regex sentinel. Moving the comment above the array aligned pytest and the sentinel.
The enrolled suite passed: 13 tests sequentially. A broader diagnostic run also exposed unrelated existing
relocation assumptions in `dev/tests/test_test_inventory.py` and pre-existing unreachable benchmark tests;
the source-connectivity path itself has zero unreachable or unnamed tests.
