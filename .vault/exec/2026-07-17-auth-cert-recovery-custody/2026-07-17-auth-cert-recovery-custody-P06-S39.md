---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S39'
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
     The S39 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Regenerate the CLI reference and operator how-to pages for the auth, certificate, and recovery families from the frozen live surface and ## Scope

- `docs/how-to/authenticate-with-aeat.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate the CLI reference and operator how-to pages for the auth, certificate, and recovery families from the frozen live surface

## Scope

- `docs/how-to/authenticate-with-aeat.md`

## Description

- Rewrite the custody sections of `docs/how-to/protect-data-access.md` to the accepted grammar: recovery create/status/verify/rotate, passphrase change, and recover, including the show-once-retype contract and the `--secrets-stdin` JSON field names.
- Replace the four retired sequence contracts with `recovery-create`, `recovery-status`, `recovery-verify`, `recovery-rotate`, and `passphrase-change` `.seq` files; update `recover.seq` to the promptable form.
- Refresh the gettext catalogues and author complete es/ca/hu translations for the changed paragraphs; the generated CLI reference regenerates from the live tree at build time (gitignored).

## Outcome

Docs build (nitpicky `-n -W`), documented-command conformance, sequence contract, catalogue drift, and all-languages completeness gates green.

## Notes

None.
