---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0f6cd140367730f3eb3848fe7109269a8d1d6a6e2374ea2df069f04079998491'
step_id: 'S47'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Add revision filing-year and period scope to census destinations and require exact scoped source mapping with Modelo 100 and 193 cross-satisfaction regressions.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Require revision id, filing year, and typed period on every census destination.
- Validate destinations against canonical law-selected revisions and exact source mappings.
- Scope closure composition and live-proof identities to the declared revision.
- Migrate the five existing destination families to published revision selectors.
- Add Modelo 100 and Modelo 193 cross-revision regressions.

## Outcome

Ruff passed. Source coverage passed 7/7, exact destination validation passed 6/6,
live proof passed 6/6, and the changed integration identity test passed 1/1.

## Notes

The broader capability discovery test is blocked by concurrent uncommitted CLI
command-spec work outside this Step at `_modelo_work_command_specs.py:208`.
