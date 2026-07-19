---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S37'
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
     The S37 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Migrate the four locale catalogues for the auth, certificate, and recovery families through the locales CLI and ## Scope

- `src/cadrumo/locales/en.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
