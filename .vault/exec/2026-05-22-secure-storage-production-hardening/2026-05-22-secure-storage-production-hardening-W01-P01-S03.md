---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W01.P01.S03`

Replaced dead security-command guidance and deprecated init guidance in the
storage custody surface with profile lifecycle guidance.

- Modified: `src/aeat/adapters/persistence/storage/errors.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/test_master_key.py`

## Description

Storage-layer missing-material and passphrase-mismatch messages now point at
profile lifecycle creation, profile switching, or the profile recovery flow.
References to the nonexistent security root and the retired config init surface
were removed from the touched storage code and tests.

## Tests

Ran:

`uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/test_master_key.py -q`

Result: 51 passed, 1 skipped.
