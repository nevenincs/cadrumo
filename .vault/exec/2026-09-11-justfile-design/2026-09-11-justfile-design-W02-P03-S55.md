---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:b1046329bd15da4d010c4410a5484f38ca2fd2f367360d5666d4dc4de3ded624'
step_id: 'S55'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose runtime-authority publication as a separately authorized mutation

## Scope

- `dev/registry/pipeline/authority_publication.py`

## Changes

- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `M` `justfile`
- `verify:` `just --dry-run registry-publish-authority` -> `pass`
