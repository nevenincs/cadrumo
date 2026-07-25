---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove mnemonic verification and recovery never serialize secret material

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`

## Description

- Add tests for the `atomically_install_verified_recovery` primitive: it installs when verify passes, preserves a prior file when verify raises, and writes nothing on an empty store when verify raises.
- Prove the persisted envelope never contains the plaintext mnemonic words or the master-key hex.
- Prove the verify and recover result records serialize without any secret material, and that a failed recover error envelope omits the mnemonic.
- Prove the recovery fingerprint carries no secret and is deterministic.

## Outcome

Mnemonic verification and recovery never serialize secret material: the on-disk envelope, both outcome records, and the error envelope are free of the plaintext mnemonic and the master key.

Evidence attributed at HEAD. Commit `f8fb73434d` ("test: prove recovery verification and recovery never serialize secrets", 2026-07-17) is the attributed landing; unlike the backend steps this test file was not part of the facade commit. At HEAD `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py` carries two classes matching the step's four claims. `TestInstallAfterVerification` holds `test_installs_payload_when_verify_passes`, `test_prior_file_survives_when_verify_raises`, and `test_no_file_written_when_verify_raises_on_empty_store`. `TestNoSecretSerialization` holds `test_persisted_envelope_never_contains_plaintext_mnemonic_or_master_key`, `test_verify_outcome_serialization_excludes_secret_material`, `test_recover_outcome_serialization_excludes_secret_material`, `test_failed_recover_error_envelope_excludes_secret_material`, and `test_recovery_fingerprint_carries_no_secret_and_is_stable`. Every claim in the step maps to a named test that exists, rather than to a count. Re-run at HEAD, `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py -m "" -q --no-header` collects 26 tests and reports 26 passed, matching the count the originating record cited; the remaining tests are the pre-existing mnemonic round-trip, key-generation, wrapping, and persistence coverage.

## Notes

Documentation reconciliation only; the tests were not re-authored. The originating record `S77` carries an identical heading and identical scope file, so the map to `S18` is exact.

The tests are class-grouped rather than module-level functions, which is why a scan for module-level `def test_` in this file returns nothing for the secret-serialization concern. That is a discovery hazard worth recording: the absence of a top-level match here is not evidence of absent coverage, and a grep-only probe would have wrongly read this step as unsubstantiated.

Real file-backed providers are used throughout; the mnemonic is captured via a confirmation callback purely to assert its absence from serialized outputs, so the assertions are genuine negative checks against a known plaintext rather than checks against a value the test never held.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
