---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:02fd9c305f7a3f04e3f49f086cba632ae527336bea389207b3d39bb01dc61ade'
step_id: 'S22'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Use complete revision metadata in the existing canonical selection rules without synthesising partial revision models

## Scope

- `src/cadrumo/domain/calculations/registry/temporal.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/temporal.py`
- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `M` `dev/registry/compiler/authority_database.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`
