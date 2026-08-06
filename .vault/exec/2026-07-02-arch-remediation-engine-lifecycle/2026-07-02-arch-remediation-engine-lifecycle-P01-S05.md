---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:67d96aad8a3013a6ef8af91ce336cd002079bf7169986f7282c025e55f6f386c'
step_id: 'S05'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Confirm the settings-driven explicit-database-URL route keeps its current direct engine path unchanged

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

- Confirm the settings-driven explicit-database-URL and root-fallback routes keep their URL-keyed direct path in `_engine_cache_key`.
- Update the adverse-session close test to assert clean bucket-identity disposal under an explicit database URL.

## Outcome

The explicit-URL route is unchanged and verified; close no longer derives a route from live settings.

Landed in commit `38e62c216`.

## Notes
