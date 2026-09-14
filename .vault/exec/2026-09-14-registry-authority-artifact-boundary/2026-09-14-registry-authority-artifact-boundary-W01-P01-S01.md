---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:fb457a74d40725210fce4b1991c1e94f414cf6ad2dc0d7d0c136fab86f12ed2a'
step_id: 'S01'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Introduce the explicit source set and expose profile-source selection through pipeline/cli.py; thread captured schema through compilation, validation, fingerprints and memo identities without ambient fallback

## Scope

- `dev/registry`

## Changes

- `M` `dev/registry/compiler/authority.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/pipeline/authority_publication.py`
- `M` `dev/registry/tests/test_authority_enrollment.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`
