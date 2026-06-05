---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S373]]'
---

# `secure-storage-production-hardening` `W12.P26.S373` Review

## S373-001 | PASS | User-profile values do not own runtime storage

`_values.py` defines strict pydantic records, lifecycle status, profile/snapshot id
helpers, typed fact coercion, and canonical snapshot hashing. It does not resolve
active profiles, inspect storage runtime, read settings, read environment variables,
open files, connect to SQL, or construct secure-object repositories.

## S373-002 | PASS | Scanner signals are model vocabulary

The `active-profile` and `manifest-bucket` signals are explained by value-model terms:
live profile roots, active/tombstoned lifecycle state, profile IDs, and comments about
bucket directories. They are not concrete manifest discovery calls.

## S373-003 | PASS | Persistence ownership remains centralized

Profile record and snapshot storage remains in the application user-profile repository
surface and secure-object runtime tests. `_values.py` provides serialized payload
shape and invariants only.

## S373-004 | FIXED | Verification tests had local import-depth regressions

Focused user-profile verification initially failed because `test_profile_repository.py`
used local imports that resolved to `aeat.application.adapters`. Those imports now
resolve to the production storage manifest modules.

## S373-005 | PASS | Validation

- `uv run --no-sync ruff check ...` passed for values, repository tests, and runtime
  storage verification surfaces.
- `uv run --no-sync pytest -q ...` passed 28 user-profile value/repository tests.
- `uv run --no-sync pytest -q ... -k "application_repository_defaults_isolate_active_profile_writes or runtime_default_surfaces"`
  passed 2 runtime storage tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-271`; `_values.py` is value-model structure, not a manifest or
active-profile storage implementation.
