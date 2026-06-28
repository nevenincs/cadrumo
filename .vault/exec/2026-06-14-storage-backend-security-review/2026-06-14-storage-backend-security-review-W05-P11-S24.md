---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S24'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Rebind the private bucket-submodule imports in profile health and overview to the bucket package surface

## Scope

- `src/aeat/application/workflow/_profile_health.py`

## Description

- Rebind `_profile_health` (5 symbols) and `_overview` (1 symbol) from the private
  `bucket._layout` / `._manifest` / `._manifest_io` submodules to the `bucket`
  package surface.

## Outcome

Private-submodule imports replaced with package-surface imports; all symbols are
in `bucket.__all__`. 146 affected-suite tests green; storage smoke (every `__all__`
name importable) green. Committed in `c22f87dbc`.

## Notes

None.
