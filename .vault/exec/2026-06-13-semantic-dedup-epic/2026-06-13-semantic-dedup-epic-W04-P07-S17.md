---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S17'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Consolidate the four identical _bucket_id active-bucket guards onto a shared resolve_active_bucket helper

## Scope

- `src/aeat/entrypoints/cli/_app_live_verify_cli.py`

## Description

- Add a shared `resolve_active_bucket(active_bucket_id, *, family)` guard to
  `_app_live_auth_preflight.py`.
- Replace the four identical `_bucket_id` guard bodies (expedientes, justificante,
  notifications, verify) with one-line delegations to the shared helper; add the
  import to each (verify gains a new import).

## Outcome

Four duplicate guard bodies collapsed to one shared helper; the per-module
`_bucket_id` wrappers delegate, so 24 call sites are unchanged. 25
live-read-subgroup tests pass; ruff clean. Landed as commit `e4568c437`.

## Notes

The remaining `_verify_expected` guard in `_app_live_verify_cli.py` is a distinct
helper (different global) and is intentionally left untouched.
