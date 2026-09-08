---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:159500e71db6a0c19a830f1813a8a2f70d8910337d1242b170af75e04d6d2c16'
step_id: 'S48'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Replace FiledDeclaracionObservation's optional opaque registry snapshot digest with required RegistrySnapshotRef and re-confirm every value-consuming read through the shared gate

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/schema.py`
- `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py`
- `src/cadrumo/application/live/filed_observation_persistence.py`
- `src/cadrumo/application/registry/filed_state.py`
- `src/cadrumo/entrypoints/cli/_overview_evidence.py`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/schema.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py`
- `M` `src/cadrumo/application/live/filed_observation_persistence.py`
- `M` `src/cadrumo/application/registry/filed_state.py`
- `M` `src/cadrumo/entrypoints/cli/_overview_evidence.py`
