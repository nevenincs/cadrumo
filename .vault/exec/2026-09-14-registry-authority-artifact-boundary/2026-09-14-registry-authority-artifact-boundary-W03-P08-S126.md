---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:c5f7a54a71d33b308821079de0c8675c179b9ebaf4d1b3411663a06d9c899d78'
step_id: 'S126'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Implement one publication acceptance suite for Windows held-reader cutover, database tamper, collisions and deferred cleanup; run it at checkpoint C

## Scope

- `dev/registry/tests/test_authority_generation_publication.py`

## Changes

- `A` `dev/registry/tests/test_authority_generation_publication.py`
- `M` `dev/registry/pipeline/authority_publication.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`
