---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S24'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S24 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
