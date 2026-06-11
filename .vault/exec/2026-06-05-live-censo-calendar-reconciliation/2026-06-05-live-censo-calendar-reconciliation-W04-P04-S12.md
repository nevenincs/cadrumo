---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-11'
step_id: 'S12'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# `live-censo-calendar-reconciliation` `W04.P04.S12` exec - noninteractive unlock fail-fast

## Scope

Step `W04.P04.S12` - Fail fast when profile-bound live CLI cannot prompt for secret-store passphrase; `src/aeat/adapters/persistence/storage/master_key/_master_key_io.py`, `src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`.

## Description

- Reproduced the profile-bound calendar CLI hang with a `faulthandler` probe and confirmed the blocked stack was `getpass.win_getpass` inside the file-fallback master-key passphrase resolver.
- Changed the default passphrase resolver to refuse when no configured passphrase exists and either stdin or stderr is not interactive, while preserving configured `Settings.aeat_secret_passphrase` resolution and explicit callback injection.
- Updated the fail-closed passphrase test to assert the noninteractive refusal instead of relying on pytest stdin capture to raise an incidental prompt error.
- Retried the real profile-bound overview calendar CLI smoke and confirmed it returns promptly with a secret-store unlock/passphrase refusal instead of hanging.

## Outcome

- `uv run pytest src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py src/aeat/adapters/persistence/storage/master_key/tests/test_master_key.py -q` passed: 62 passed.
- `uv run ruff check src/aeat/adapters/persistence/storage/master_key/_master_key_io.py src/aeat/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py` passed.
- `uv run aeat --format json app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` now exits in about 3 seconds with `AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive`.

## Notes

- This step removes the CLI deadlock but does not unlock the encrypted profile store. W04.P04.S09, S10, and S11 remain open until a noninteractive passphrase/keychain session is available and the authenticated censo/filed-history/messages/justificante/calendar proof is rerun.
- The `vaultspec-core vault plan step add/check` commands persisted the plan changes but again exited with the known cache-invalidation `LookupError` caused by an unset vault CLI workspace context.
