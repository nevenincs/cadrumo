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
