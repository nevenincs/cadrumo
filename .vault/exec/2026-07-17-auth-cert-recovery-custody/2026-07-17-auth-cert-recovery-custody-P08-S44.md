---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S44'
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
     The S44 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The DEFERRED until the operator P04 passphrase door commits: make certificate secret set reject the passphrase as an argv value and read it only via the hidden prompt or bounded stdin, reusing the P04 door _secure_input.py bounded-stdin no-echo infrastructure rather than building a parallel secret-input authority, gated on a test proving the passphrase cannot be supplied as an argv value and is read only through hidden prompt or bounded stdin and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DEFERRED until the operator P04 passphrase door commits: make certificate secret set reject the passphrase as an argv value and read it only via the hidden prompt or bounded stdin, reusing the P04 door _secure_input.py bounded-stdin no-echo infrastructure rather than building a parallel secret-input authority, gated on a test proving the passphrase cannot be supplied as an argv value and is read only through hidden prompt or bounded stdin

## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py`

## Description

- Remove the `--secret` argv option from `certificate secret set`; the PKCS#12 passphrase now arrives only via the hidden no-echo prompt or one bounded strict-JSON `--secrets-stdin` object, reusing the shared `_secure_input` channel (no parallel secret-input authority).
- Migrate every `test_certificate.py` invocation to the stdin channel and add gates proving the argv passphrase is refused, the no-TTY/no-stdin path refuses cleanly naming `--secrets-stdin`, and the help names only secure channels.

## Outcome

Certificate suite green (16 tests including 3 new gates); the passphrase can no longer land in the process table or shell history.

## Notes

Landed after the P04 passphrase door committed, per the Step's deferral condition.
