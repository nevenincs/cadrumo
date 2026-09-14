---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:629e929015ec408cc5b8f8a2697b513165afcaed80918c69288bdca093fa44e5'
step_id: 'S66'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Migrate calculation, carry, annual-summary, observation and cross-period consumers using the reviewed model-lane file inventory

## Scope

- `src/cadrumo/application/calculations`

## Changes

- `M` `src/cadrumo/application/calculations/revision_carry_gate.py`
- `M` `src/cadrumo/application/calculations/relation_prefill_m202.py`
- `M` `src/cadrumo/application/calculations/m303_regimen_simplificado.py`
- `verify:` `checkpoint B integrated model selection` -> `pass`
