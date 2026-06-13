---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S25'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P07.S25 extract work-calculate typed input assembly

Scope: `W03.P07` modelo work calculate input preparation.

## Description

- Add `WorkCalculateInputBundle` as the typed application-facing bundle for `modelo work calculate`.
- Freeze operator-supplied casilla, binding, enum-binding, relation, detail-row, and borrador snapshot inputs before calling the calculation service.
- Centralize the optional mapping conversion currently required by `calculate_modelo_revision_from_bucket_aggregation`.

## Outcome

The calculate command now crosses into the application calculation boundary through a named typed bundle instead of a loose cluster of local dictionaries.

## Notes

The bundle is intentionally narrow and has no calculation logic. It only normalizes ownership and optionality for data already parsed by the CLI command.
