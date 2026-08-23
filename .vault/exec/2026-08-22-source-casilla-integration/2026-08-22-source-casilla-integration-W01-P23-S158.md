---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6043f57685f227da4e5e657a4a31ab86d109e20d6f00c91c435f052d3fb877bc'
step_id: 'S158'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# emit deterministic per-capability census membership and reviewed disposition evidence for aggregate coverage buckets

## Scope

- `dev/source_connectivity/cli.py`

## Description

- Retain the validated manifest and deterministic assignments in the successful check result.
- Project one output record per discovered capability in stable identity order.
- Carry the owning candidate, closed disposition, decision reason, and grounding references on every record.
- Include the complete membership ledger in comparison JSON instead of reporting counts alone.

## Outcome

Aggregate census buckets are now inspectable at per-capability granularity. An operator or later audit can
trace every capability to its owning row, reviewed disposition, reason, and re-fetchable grounding while
the canonical manifest remains compact and authoritative.

## Notes

Ruff passed, the projection unit test passed, and a live explicit-candidate projection produced 16 stable
records. Full selector projection remains correctly blocked by the concurrent ingress-surface drift rather
than refreshing its digest from peer work in progress.
