---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S01'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden authenticate-with-aeat.md and ## Scope

- `docs/how-to/authenticate-with-aeat.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden authenticate-with-aeat.md

## Scope

- `docs/how-to/authenticate-with-aeat.md`

## Description

- Verify-close: read `authenticate-with-aeat.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M22 (over-states provider support): the page now marks each provider `disponible` vs `reservado (no disponible aún)` via `aeat config auth providers` - `certificate`, `clave_movil`, and `clave_permanente` are available (ClavePermanente was subsequently wired), `clave_pin` reserved - rather than presenting all five as usable.
- Confirm the master-key passphrase prerequisite is stated, `--file` is the file-input option (per the cli-pull-and-file standard), and the certificate-expiry/renewal guidance is present.

## Outcome

- Page verified compliant at HEAD; finding M22 resolved (2026-06-19 documentation batch; the available set updated to reflect the wired ClavePermanente provider). Delta: none required.

## Notes

- S-AUTH (auth-unconfigured refusal wording) is addressed on the companion read-live page; the apoderado section is accurate per the audit. CLI conformance gate green.
