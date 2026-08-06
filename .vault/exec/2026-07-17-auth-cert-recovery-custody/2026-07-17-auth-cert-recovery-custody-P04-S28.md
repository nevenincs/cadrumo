---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:69c68de97c51baa1542300c4414d29525ceaee5f58b687b65cefe38da971b4be'
step_id: 'S28'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`

## Description

- Author `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`: a real-entrypoint subprocess harness over a real encrypted vault.
- Round-trip status (unenrolled to enrolled with fingerprint), create-refuses-second-enrollment, verify yes/no via `--secrets-stdin`, rotate (old code dies, new code verifies, fingerprint changes), flat recover binding a new passphrase, and profile readability under the recovered passphrase.
- Assert the mnemonic never appears in any CLI stdout/stderr, JSON envelope, or the persisted wrapper file.
- Prove non-interactive create/rotate refuse with the prior envelope byte-identical, strict bounded-JSON stdin refusals, and passphrase-mismatch / wrong-code refusals that leave the vault intact.

## Outcome

Five integration tests green; the enrollment half drives the production `create_recovery_code`/`rotate_recovery_code` operations with a real confirm callback (the CLI create/rotate verbs are TTY-only by design, so the captured harness proves their refusal path).

## Notes

Windows quirk: the `NUL` device reports as a TTY, so the harness pipes stdin (empty when no payload) to get the genuine redirected-stdin condition; an inherited console handle would block on the hidden prompt.
