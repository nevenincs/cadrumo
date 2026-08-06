---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:42743eb9ba772abba47fd863e7853740cb0d99a8809ccc46a27ce67969332d7b'
step_id: 'S37'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Migrate the four locale catalogues for the auth, certificate, and recovery families through the locales CLI

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Migrate the four locale catalogues for the recovery family through the locales CLI only: scaffold, then real en/es/ca/hu copy for the `cli.config.recovery.*` help/prompt/error keys, the recover stdin errors, and the certificate secret prompt.
- Remove the retired keys (`show_recovery.*`, `verify_recovery.*`, `recover.recovery_key_help`, the argv-passphrase custody keys, `rekey.help`, the certificate `secret_help`).

## Outcome

`python -m cadrumo.locales scaffold --check` and `audit` report ok for all four catalogues; parity and honesty gates green.

## Notes

The `cli.config.custody.new/confirm_new_passphrase_prompt` allowlist entries in the locale prose-key audit were dropped with their keys.
