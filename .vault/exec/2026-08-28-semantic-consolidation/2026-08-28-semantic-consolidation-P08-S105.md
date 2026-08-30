---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:532c89424cb7a40caecc713a3ae4303d39091aa28fbb2b6665e112470cffb579'
step_id: 'S105'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the Exonerado-390 canonical-owner pin at the module that defines those classes rather than the one that had gone on re-exporting them after they moved

## Scope

- `src/cadrumo/application/filing/tests/`

## Changes

- `M` `src/cadrumo/application/filing/tests/test_m303_export_applicability_internal.py`
- `verify:` `pytest src/cadrumo/application/filing/tests/test_m303_export_applicability_internal.py -n 0 -m ""` -> `pass`

## Notes

The pin survived a rename sweep unchanged in meaning but wrong in fact: it named
`calculation_revision`, which had stopped defining these classes and only went
on re-exporting them. Repointing the sweep preserved the wrong module, and only
removing the re-export made the gate say so.
