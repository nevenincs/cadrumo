---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:b31481e2df4f891a511d4536b16bd9ab2a81c63c97531822b811cd2123d140c8'
step_id: 'S111'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`

## Description

The full recovery-code lifecycle (`recovery status`, `create`, `rotate`, `verify`, and
flat `recover`) needed a real-encrypted-vault round-trip proof that no surface ever
serializes the 24-word mnemonic.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py` proves the full
lifecycle against real secret-store files: `test_recovery_lifecycle_round_trips_without_serialized_mnemonic`
(lines 207-313) walks status(unenrolled) -> create -> status(enrolled, both text and JSON
envelopes) -> verify(correct/incorrect) -> rotate -> verify(old code now rejected, new code
accepted) -> recover(with the rotated code) -> profile show under the recovered
passphrase -> status(fingerprint unchanged, proving recover reads rather than rewrites the
envelope). It asserts the mnemonic never appears in the persisted envelope file or in any
CLI stdout/stderr. Companion tests cover: refusal without an interactive terminal for
create/rotate leaving the envelope byte-identical (lines 315-343); strict bounded
`--secrets-stdin` JSON (malformed, wrong-field, non-object payloads all refuse, lines
345-371); an 8192-byte oversize-payload refusal (lines 373-395); a duplicate-JSON-key
refusal rather than silent last-value acceptance (lines 397-426); passphrase-mismatch and
wrong-recovery-code refusals on `recover` leaving the vault untouched (lines 428-464); and
`test_recovery_verbs_accept_no_mnemonic_argv` (lines 467-477) proving the retired
`--recovery-key` argv channel is gone from both `recover` and `recovery verify`.

## Notes

File matches the step's declared scope exactly. Cited the coordinator's gate run rather
than re-executing the full suite (serial `-n0` lane 27 passed/1 failed, the one failure
being the unrelated S112 help-secrets gap). This module carries `pytest.mark.integration`
and `pytest.mark.hex_entrypoint` (not `os_keychain`), so it runs under the standard
`-m "integration and not os_keychain"` selection.
