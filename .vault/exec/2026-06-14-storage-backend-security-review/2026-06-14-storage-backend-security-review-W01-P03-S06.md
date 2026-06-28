---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S06'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Delete the dead non-atomic _write_bytes_secure method and its sensitive-persistence-policy allowlist entries

## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key.py`

## Description

- Delete the dead `_write_bytes_secure` static method (no production caller; the
  live primitive is `_write_bytes_secure_fd` in `_materialisation.py`).
- Remove its two `os.open` / `os.write` sensitive-persistence-policy allowlist
  entries.

## Outcome

Dead non-atomic write surface removed; policy gate green. Committed in `e6f280e68`.

## Notes

DEFERRED (owner-gated): the write-only standalone `salt` artefact removal was
split out to `W01.P03.S32`. The `salt` file is redundant for KEK derivation (the
real salt is `master.kdf.salt_b64`) but is load-bearing for the 3-artefact
torn-install detection tuple and is asserted by `test_explicit_provision_mints_and_persists`.
Per the `no-legacy-compatibility` key-management caution, key-store-adjacent
deletions are owner-gated, not autonomous.
