---
step_id: S266
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P11.S266 — RepositorySetupError introduction

## Scope

Replace the `TypeError` programming-contract guard at
`src/aeat/adapters/persistence/storage/envelope/_secure_repository.py:105`
with `RepositorySetupError(RepositoryError)`, a typed error enrolled in
`ERROR_REGISTRY` so it produces a structured envelope rather than an
opaque interpreter-level exception.

## Outcome

### New error class

`RepositorySetupError(RepositoryError)` added to
`src/aeat/adapters/persistence/storage/errors.py` after `RepositoryError`.

### Registry entry

`aeat.adapters.persistence.storage.errors.RepositorySetupError` registered
in `src/aeat/core/errors/registry/_adapters.py` with:
- code: `FAIL_STORAGE_REPOSITORY_SETUP`
- category: `FAIL`
- message_key: `errors.fail.fail_storage_repository_setup`

### Raise site updated

`_secure_repository.py` now imports `RepositorySetupError` and raises it
instead of `TypeError` in the class-attribute guard loop.

## Locale keys

`errors.fail.fail_storage_repository_setup` added to all locale files via
`python -m aeat.locales set` + `scaffold`.

## Files touched

- `src/aeat/adapters/persistence/storage/errors.py`
- `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`
- `src/aeat/core/errors/registry/_adapters.py`
- `src/aeat/locales/*.yml`

## Collision signal

`git diff -- <target files>` before edits: no output (clean).
