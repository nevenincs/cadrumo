---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S22'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Replace config rekey with only config passphrase change and secure input handling

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

Verified against HEAD `8af409cd3f`, no re-implementation needed:

- Confirmed `_custody_secret.py` registers `_register_passphrase_commands` exposing only `config passphrase change`; no `rekey` verb is registered anywhere in the CLI (the only surviving `rekey` tokens repo-wide are historical-migration prose in `test_root_grammar_invariants.py` asserting the old verb is gone).
- Confirmed `passphrase_change` reads its secrets exclusively via `_resolve_passphrase_change_secrets`, which routes through `._secure_input` (`read_secrets_stdin` / `prompt_secret_no_echo`) — never `argv` — matching the module's own "secure input handling" docstring contract.

## Outcome

Verified complete, zero production-code changes needed. `config rekey` does not exist; `config passphrase change` is the sole passphrase-rotation verb and its secret handling is bound to the shared `_secure_input` channel.

## Notes

Bookkeeping-only closure: this record documents verification, not new implementation.
