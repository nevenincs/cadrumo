---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S107'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

The old `config verify-recovery` spelling had to be replaced by `config recovery verify`
plus the flat `config recover` execution verb, both reading the 24-word recovery code only
through the shared secure-input channel, never as an ordinary `argv` value.

## Outcome

`recovery_verify` (`src/cadrumo/entrypoints/cli/_config/_custody_secret.py:358-399`) and
`config_recover` (`_register_recover_command`, lines 242-289) are the only two commands
that accept a recovery code; both resolve it exclusively through `_resolve_recovery_code`
(lines 171-179) or `_resolve_recover_secrets` (lines 182-201), which read from
`--secrets-stdin` strict models (`_RecoveryVerifySecrets`, `_RecoverSecrets`, both
`extra="forbid"` `SecretStr` fields) or a no-echo prompt — no `typer.Argument`/`Option`
ever declares the code as a plain string. No `config verify-recovery` registration exists
anywhere in `src/cadrumo/entrypoints/cli` (zero `rg` hits in production code), and
`test_recovery_verbs_accept_no_mnemonic_argv`
(`src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py:467-477`) proves the
retired `--recovery-key` argv channel is gone from both `recover` and `recovery verify`.

## Notes

Verified by direct file reads of `_custody_secret.py` and the corresponding lifecycle test.
Cited the coordinator's gate run (serial `-n0` lane 27 passed/1 failed, the failure being
the unrelated S112 gap) rather than re-executing. RAG code index remains degraded; `rg` and
direct reads were the verification instrument.
