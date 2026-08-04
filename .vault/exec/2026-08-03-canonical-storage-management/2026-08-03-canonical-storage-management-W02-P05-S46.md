---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a23618eeeed3b0d29892c1b3355a7b1e25ef8f68bc5a986122181492107db8a1'
step_id: 'S46'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the Playwright browser root as a third-party-owned-cache escape carrying its role, gated by a test asserting the escape is declared and that the resolver still honours the vendor environment variable

## Scope

- `src/cadrumo/application/provisioning.py`

## Description

## Outcome

Landed in `b3015bda3e`, confirmed at HEAD. `PLAYWRIGHT_BROWSERS_ROOT_ROLE = ExternalPathRole.THIRD_PARTY_CACHE` in `src/cadrumo/application/provisioning.py:168` declares the escape with a docstring explaining Playwright's vendor-owned layout (lines 169-183). Gated by `application/tests/test_provisioning.py`, confirmed to still honour the vendor environment variable.

## Notes
