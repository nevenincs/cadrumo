---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:668a7d51b8e8a44544851b94e904e50e31ac408fa19f01523b0db0ac51ef598b'
step_id: 'S24'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

- Register only `config recovery verify` and the flat `config recover`; delete `verify-recovery` and every mnemonic/passphrase argv option (`--recovery-key`, `--new-passphrase`, `--confirm-new-passphrase`).
- Read the recovery code and the recover passphrases exclusively through the shared secure-input channel: strict `extra=forbid` SecretStr models over one bounded `--secrets-stdin` JSON object, or no-echo terminal prompts.
- Map a non-matching recovery code to a localized refusal; a new/confirmation passphrase mismatch refuses before any custody mutation.
- Sweep the operator-surface contract, risk table, repair-policy catalog, bootstrap exemptions, master-key error texts, error-registry suggestion, and four locale catalogues onto the new grammar.

## Outcome

No secret can reach any recovery verb as an argv value; verify and recover consume the same bounded stdin / no-echo channels the passphrase family established.

## Notes

The `errors.auth.auth_storage_master_key_passphrase_mismatch` copy and the `AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION` default suggestion were re-pointed at the promptable `aeat config recover`.
