---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:c01309310183644bd53385a4f4e80adb01241102c69ee29b4667a0c255540e13'
step_id: 'S92'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Migrate IVA facts, vocabulary, catalogues and evidence to requested components while preserving dated resolution

## Scope

- `src/cadrumo/domain/iva`

## Changes

- `M` `src/cadrumo/domain/iva/classification.py`
- `M` `src/cadrumo/domain/iva/components.py`
- `M` `src/cadrumo/domain/iva/lookup.py`
- `M` `src/cadrumo/domain/iva/rates.py`
- `verify:` `checkpoint B focused import and contract checks` -> `pass`
