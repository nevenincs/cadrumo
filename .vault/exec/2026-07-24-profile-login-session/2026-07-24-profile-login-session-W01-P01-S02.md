---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:5e1760f855bea3fa6fa4314de4f657ee3672645391cc92ce9427b765b9741380'
step_id: 'S02'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Add the cadrumo_bucket_default_session_absolute_minutes Settings field (default 240, validated 60 to 720) and the session_absolute_minutes bucket-manifest override with a resolver mirroring idle_minutes_for_bucket, threading the resolved cap into _provider_enter, verified by settings-validation tests and a provider-enter test observing the configured cap on the opened session

## Scope

- `src/cadrumo/core/config.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`

## Description

- Add the `cadrumo_bucket_default_session_absolute_minutes` Settings field beside `cadrumo_bucket_default_idle_lock_minutes` (default 240, validated `gt=0`, `ge=60`, `le=720`).
- Add the `session_absolute_minutes` optional bucket-manifest override and serialise/hydrate it through the manifest IO round-trip.
- Add the `session_absolute_minutes_for_bucket` resolver mirroring `idle_minutes_for_bucket` (manifest value else settings default).
- Thread the resolved cap through `_provider_enter` into `BucketSession.open(absolute_minutes=...)`.
- Extend the shared test helper for the new manifest override; add settings default + range-bound tests and provider-enter tests observing the configured cap (manifest override and settings fallback) on the opened session.

## Outcome

Landed in commit `9dad0cbe8b` (subject mislabelled `@` per the shared-worktree amend incident; content correct). `ruff check` clean; the new `test_session_absolute_minutes_setting.py`, `test_external_constants.py`, the provider-enter cases in `test_master_key_file_fallback.py`, and the full `bucket/tests` (109) and `master_key/tests` (231) suites pass under sequential `-n0`; `collect-only` over `master_key` + `core` is clean (992 collected).

## Notes

The manifest field is optional (`None` default, omitted from serialised TOML when unset), so existing manifests round-trip unchanged and the change is byte-stable. The cap lives on `Settings` per `aeat-schema-central-config`, not as an inline literal. Commit-message mislabel logged by the coordinator; history left as-is per direction.
