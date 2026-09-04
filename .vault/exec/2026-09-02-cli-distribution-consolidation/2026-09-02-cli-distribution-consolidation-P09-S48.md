---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:f8900df83fe922cf8f7621fdc49ef7ffda7ff726d673f1d2af05ecb9528fa818'
step_id: 'S48'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Separate the seal check from the publication check and guard the upload with the authority that names it

## Scope

- `dev/release/version_identity.py`

## Changes

- `M` `dev/release/version_identity.py`
- `M` `dev/release/tests/test_version_identity.py`
- `A` `dev/release/tests/test_publish_workflow.py`
- `M` `dev/packaging/tests/test_packaging_smoke_workflow.py`
- `M` `.github/workflows/publish.yml`
- `M` `.github/workflows/packaging-smoke.yml`
- `M` `Dockerfile`
- `M` `dev/containers/runner_capabilities.py`
- `M` `dev/runners/runner-entry-linux.sh`
- `M` `dev/runners/README.md`

## Scope

- `dev/release/version_identity.py`

## Changes
