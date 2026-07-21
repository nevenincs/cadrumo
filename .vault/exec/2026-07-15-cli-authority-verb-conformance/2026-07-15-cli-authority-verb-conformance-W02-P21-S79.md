---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S79'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove passphrase change preserves encrypted data and survives failed candidate confirmation

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`

## Description

- Add a test proving a passphrase change (the file provider's rewrap under a new passphrase) preserves the master key: a record encrypted before the change still decrypts after, the store opens under the new passphrase, and the old passphrase no longer opens it.
- Add a test proving a rejected candidate passphrase is refused before any artefact is rewritten, leaving the on-disk key artefact byte-identical, the store openable under the established passphrase, and the encrypted record intact.

## Outcome

Passphrase change preserves encrypted data and fails closed on a bad candidate. `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py -q` reports 5 passed.

## Notes

At the master-key layer the fail-closed guarantee is that the provider validates the new passphrase before mutating any artefact; the confirmation-mismatch retype is the CLI-level analogue migrated in a later wave.
