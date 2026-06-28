---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S50'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P13.S50 Exact Centralized Addressing Audit

Scope: run exact search for raw-id regexes, local selector branching, and decentralized revision-pick handling.

## Description

- Search modelo CLI modules for raw id regexes, direct work-address constructors, low-level calculation-revision address resolvers, workflow-period lookup, latest-run lookup, and current-revision pointer access.
- Verify raw exact-id regex hits are confined to `_modelo_cli_support.py`.
- Verify remaining `current_calculation_revision_id` hits are rendering, payload, or test assertions rather than selector policy.
- Verify centralized facade calls appear in `_modelo.py`, `_modelo_export_cli.py`, `_modelo_work_runs_cli.py`, `application.modelo`, and `application.workflow`.

## Outcome

Exact discovery supports the closure claim: CLI resolver policy now flows through centralized facades, with raw-id validation isolated to shared CLI support and output-only identifier fields remaining in render/payload surfaces.

## Notes

No production CLI module imports private application or domain selector modules for the migrated addressing path.
