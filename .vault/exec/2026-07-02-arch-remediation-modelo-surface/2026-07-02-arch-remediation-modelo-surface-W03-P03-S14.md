---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:590f270afe3a9b0ce482b9ef48ca3f9b5a32006991a6a4f7443345409c3ed06a'
step_id: 'S14'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Declare the calculate-path precedence ladder as ordered tier data carrying tier name, owned sources, and override disposition in the aggregation package

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Add `CallerOverrideDisposition` (LOCK/CARRY), `CallerOverridePrecedenceTier`, and the ordered `CALLER_OVERRIDE_PRECEDENCE_LADDER` tuple plus `precedence_ladder_sources()` to the aggregation source-mesh package.

## Outcome

The caller-override precedence ladder is declared once as ordered tier data (name, owned source kinds, override disposition), co-located with `DEFERRED_SOURCE_KINDS`. Commit `ddda33609`.

## Notes
