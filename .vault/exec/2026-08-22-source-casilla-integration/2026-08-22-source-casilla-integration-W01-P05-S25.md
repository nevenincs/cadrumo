---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:978ce99c2c42d67f0488b03c3bd83f27b89fa028a83a5f5de475a40fb8e601c9'
step_id: 'S25'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# reject unclassified new source capabilities and unexplained candidate disappearance

## Scope

- `dev/source_connectivity/check.py`

## Description

- Add a reusable monotonic census check over live independent discovery.
- Convert unknown, removed, duplicated, unclaimed, and selector-drifted capabilities into a typed gate failure.
- Route the comparison CLI through the same check authority used by later quality gates.

## Outcome

Capability growth and unexplained disappearance now share one fail-closed check authority. The live tree
passes with 428 discovered capabilities, 428 assignments, and 14 reviewed census entries; any mismatch
raises `SourceConnectivityCheckError` and the comparison command exits nonzero.

## Notes

Ruff and the live reusable check passed. The combined verification command reached its time budget after
the CLI comparison, so the direct check invocation was rerun independently and completed successfully.
