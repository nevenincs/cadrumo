---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S25'
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
     The S25 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

- Write the candidate recovery words directly to the controlling terminal device (`CONOUT$` / `/dev/tty`) via the new `write_to_controlling_terminal` in `src/cadrumo/entrypoints/cli/_config/_secure_input.py`, deliberately bypassing stdout so a redirected stream, JSON envelope, or log can never serialize them.
- Require a full no-echo retype of all 24 words before commit; the storage facade verifies the retype against the staged envelope and installs atomically only on match.
- Refuse `create`/`rotate` cleanly (REFUSED, exit 2, localized) when stdin is not an interactive terminal, before any custody read.

## Outcome

Enrollment is show-once-retype-to-commit: a cancelled, mistyped, or non-interactive attempt leaves the prior envelope byte-identical.

## Notes

The terminal write is registered as an audited exception in the output-surface inventory gate with the secret-serialization rationale.
