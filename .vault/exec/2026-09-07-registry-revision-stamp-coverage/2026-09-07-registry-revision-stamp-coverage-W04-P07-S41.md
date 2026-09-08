---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f26814ccd9277865cc3aab33f6f8082d2d382406a9dc2861ef3e00b7f089c253'
step_id: 'S41'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Delete optional-stamp defaults, missing-coordinate advisory branches, the deprecated FiledDeclaracionObservation registry_snapshot_id digest field, and compatibility deserializers exposed by this campaign

## Scope

- `src/cadrumo/application`
- `src/cadrumo/adapters/persistence`
- `src/cadrumo/adapters/outbound/aeat/sede`

## Changes

- `M` `src/cadrumo/application/calculations/revision_carry_gate.py`
- `M` `src/cadrumo/application/calculations/observations_repository.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/schema.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py`
