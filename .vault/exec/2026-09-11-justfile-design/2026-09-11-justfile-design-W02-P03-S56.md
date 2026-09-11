---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:99eff01f8bd60f89d87773648df39cd239a048bb00e6d23ca17a6099809863c6'
step_id: 'S56'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose target publication and digest-bound republishing as separately authorized mutations

## Scope

- `dev/registry/pipeline/_tree_publication.py`

## Changes

- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `M` `justfile`
- `verify:` `just --dry-run registry-publish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
- `verify:` `just --dry-run registry-republish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A EXPECTED_MANIFEST_SHA256` -> `pass`
