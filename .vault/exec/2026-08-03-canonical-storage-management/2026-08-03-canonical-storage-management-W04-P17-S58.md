---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5b39bd3e3634579cb71735c3da7b27d10cf31dc596a65e7a98de5b40bf1a4a26'
step_id: 'S58'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the config storage family bootstrap-exempt rather than profile-bound, because the guard returns its exemption before consulting the guarded catalogue and a guarded entry would both be unreachable and make init refuse on a fresh machine, gated by a test asserting the exemption and one asserting init succeeds with no active profile

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Description

- Declare the `config storage` family bootstrap-exempt in `_bootstrap_exempt.py` rather than profile-bound, per ADR R21 (the family must materialise the tree before a profile exists, and the guarded catalogue is unreachable from a bootstrap-exempt path anyway).

## Outcome

Landed in commit `ecd388183f`; checkbox corrected here.

## Notes
