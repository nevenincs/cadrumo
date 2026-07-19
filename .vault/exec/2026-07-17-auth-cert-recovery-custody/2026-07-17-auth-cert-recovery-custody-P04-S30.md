---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S30'
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
     The S30 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`

## Description

- Extend `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py` with a parametrized contract that every custody secure-input refusal key (non-interactive secret, stdin too large / invalid JSON / missing fields, interactive-terminal-required, retype mismatch, recovery-code rejected) resolves to non-placeholder operator copy.
- Prove strict bounded `--secrets-stdin` behavior through localized CLI execution in the recovery lifecycle suite: malformed JSON, non-object payloads, and unexpected fields refuse (exit 2) with no traceback.

## Outcome

Secure-TTY and bounded-stdin failures surface as localized REFUSED exits across the recovery family.

## Notes

None.
