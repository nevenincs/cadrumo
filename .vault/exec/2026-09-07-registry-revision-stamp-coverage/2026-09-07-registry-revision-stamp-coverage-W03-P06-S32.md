---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:83326044f490d75564111ebf19be969cb79b74c613a259314c21e66ba3a59701'
step_id: 'S32'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Require an explicit tuple of canonical source RegistrySnapshotRef values on ProrrataRegisterEntry, empty only when the entry contains no registry-derived source value

## Scope

- `src/cadrumo/domain/prorrata_register/register.py`

## Changes

- `M` `src/cadrumo/domain/prorrata_register/register.py`
