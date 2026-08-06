---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:1396281046eed8bd892928b969f8d81926b0af9db20e8ac81bf8c3193e005a74'
step_id: 'S20'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove passphrase change preserves encrypted data and survives failed candidate confirmation

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`

## Description

- Add a test proving a passphrase change, the file provider's rewrap under a new passphrase, preserves the master key: a record encrypted before the change still decrypts after, the store opens under the new passphrase, and the old passphrase no longer opens it.
- Add a test proving a rejected candidate passphrase is refused before any artefact is rewritten, leaving the on-disk key artefact byte-identical, the store openable under the established passphrase, and the encrypted record intact.

## Outcome

Passphrase change preserves encrypted data and fails closed on a bad candidate.

Evidence attributed at HEAD. Commit `5bf6a3403a` ("test: prove passphrase change preserves data and fails closed on bad candidate", 2026-07-17) is the attributed landing. At HEAD `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py` carries `test_passphrase_change_preserves_master_key_and_encrypted_data` and `test_rejected_candidate_passphrase_leaves_store_openable_and_data_intact`, alongside three pre-existing passphrase-handling tests.

Both new tests were read at HEAD rather than accepted on their names. The first encrypts a record under the provisioned master key, rewraps through `complete_recovery` under a new passphrase, then asserts the reopened provider returns the same master key, that the pre-change ciphertext still decrypts, and that the old passphrase now raises `MasterKeyPassphraseMismatchError`. The second captures the `master.key` bytes before the attempt, drives a too-short candidate to a `PassphraseTooShortError`, then asserts the key artefact is byte-identical, the store still opens under the established passphrase, and the record still decrypts. Both use real encryption and a real on-disk file provider, so neither is tautological. Re-run at HEAD, `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py -m "" -q --no-header` collects 5 tests and reports 5 passed, matching the count the originating record cited.

## Notes

Documentation reconciliation only; the tests were not re-authored. The originating record `S79` carries an identical heading and identical scope file, so the map to `S20` is exact.

A scope caveat is recorded here rather than smoothed over. The step's wording is "survives failed candidate confirmation", and at this layer that is proven as candidate *rejection* — a too-short passphrase refused by validation before any artefact is written — not as a retype *confirmation mismatch*. The master-key layer has no retype concept to fail; the operator retype and its mismatch path are the CLI-level analogue, carried by the P04 door step covering no-echo retype before commit. The originating record disclosed the same narrowing at the time, so this is a known and deliberate layer split rather than a silent shortfall. The consequence for a reader is that this step alone does not evidence retype-mismatch behaviour, and the P04 door step must be read alongside it for that half of the guarantee.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

Substantiation is complete for the preservation and fail-closed-on-rejection claims, and partial for the "confirmation" reading of the step wording, per the caveat above.
