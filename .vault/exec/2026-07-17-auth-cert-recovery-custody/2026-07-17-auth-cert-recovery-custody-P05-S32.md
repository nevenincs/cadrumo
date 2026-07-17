---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S32'
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
     The S32 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface

## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py`

## Description

Verified the certificate CLI door in `_config/_certificate.py` is already at the accepted grammar target and requires no further change; the certificate-keyring backend deletion (phase P02) already stripped every backend-selection surface from the door.

- Confirmed the `certificate secret set` and `certificate secret remove` verbs expose only `--name` (and the prompted, hidden `--secret` on `set`); there is no `--backend` option, no backend-selection enum, and no keyring/migration/fallback subcommand.
- Confirmed the secret mutation routes solely through the encrypted secure-storage backend via `set_operator_certificate_source_secret` / `remove_operator_certificate_source_secret`, addressing the selected profile's secure storage with no keyring selector, reconciliation prerequisite, or fallback path.
- Confirmed the door exposes no compatibility alias or migration surface: the real-CLI test `test_certificate_secret_cli_exposes_no_backend_or_legacy_grammar` proves `--backend keyring` returns "No such option" (exit 2) and the retired `keyring`/`migrate`/`fallback`/`probe`/`clear`/`put`/`delete` subcommands return "No such command".

## Outcome

Step satisfied against the current tree with no code change to the door file. The vestigial `backend` label field still projected on the result payload is out of this step's scope (`_config/_certificate.py`); it is the certificate-payload projection tracked by P06.S35 (`_config_payloads.py`) and left for that step. Evidence: `test_certificate.py` runs green (13 passed under the serial integration pass).

## Notes

Verify-and-close backed by the committed door state and the comprehensive real-behavior test. The door reached target during the P02 certificate-keyring backend deletion; this step confirms and records it under the plan's own feature stem per the plan-closure-requires-exec-records discipline. No mock/stub/skip used; the test drives the real Typer tree against real encrypted secure storage.
