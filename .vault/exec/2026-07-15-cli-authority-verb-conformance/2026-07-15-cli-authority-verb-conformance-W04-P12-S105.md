---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:dcfd8d698f5eeeb5cbdd7f99291ef53045d8b13869bd6f7474c7476dbbe5a307'
step_id: 'S105'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace config rekey with only config passphrase change and secure input handling

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

The old `config rekey` spelling had to be replaced by a single `config passphrase change`
transport command that reads the three passphrases only through the shared secure-input
channel (no-echo terminal prompt or one bounded `--secrets-stdin` JSON object), never as an
`argv` value.

## Outcome

`register_secret_custody_commands` in `src/cadrumo/entrypoints/cli/_config/_custody_secret.py:459-463`
registers exactly the `passphrase` subgroup, the flat `recover` verb, and the `recovery`
subgroup; `_register_passphrase_commands` (lines 79-140) exposes only `passphrase change`,
whose body (`_resolve_passphrase_change_secrets`, lines 55-76) reads
`current_passphrase`/`new_passphrase`/`new_passphrase_confirmation` from
`_PassphraseChangeSecrets` (a strict `extra="forbid"` model of `SecretStr` fields) or from
no-echo prompts, and refuses on a new/confirmation mismatch before any custody mutation. No
`config rekey` registration, string, or alias exists anywhere in
`src/cadrumo/entrypoints/cli` (confirmed by `rg "config rekey"` returning no production
hits) and no `--secret`/plain-argv passphrase option is declared on the command.

## Notes

Verified by reading the module directly and by `rg` across
`src/cadrumo/entrypoints/cli` for the retired `rekey` spelling (zero production hits;
only test-file references to the retired spelling as a negative assertion target). Cited
the coordinator's gate run rather than re-executing it: parallel lane 154 passed/1 failed
and serial lane (`-n0`) 27 passed/1 failed, both failures being the unrelated S112 secrets
help gap owned by another agent. The code index used for discovery
(`vaultspec-rag --type code`) is known truncated (~1027/4546 files); this record relies on
direct `rg`/file reads, not RAG hits.
