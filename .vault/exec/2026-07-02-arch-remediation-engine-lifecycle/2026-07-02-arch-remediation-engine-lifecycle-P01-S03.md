---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Re-key the engine cache on bucket identity rather than raw database URL, keeping the URL an implementation detail of engine construction

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

- Re-key the engine cache on bucket identity (resolved storage root + bucket id) in `_engine_cache_key`.
- Keep the URL key for explicit-database-URL and root-fallback routes.

## Outcome

Bucket-routed engines cache by identity; the database URL is an engine-construction detail.

Landed in commit `38e62c216`.

## Notes
