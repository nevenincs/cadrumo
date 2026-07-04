---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S23'
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
     The S23 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden protect-data-access.md and ## Scope

- `docs/how-to/protect-data-access.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden protect-data-access.md

## Scope

- `docs/how-to/protect-data-access.md`

## Description

- Verify-close: read `protect-data-access.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm the audit's positive verdict: the protect-data-access flow delivered fully end-to-end (show-recovery, verify-recovery, passphrase `--rotate`, rekey-without-re-encrypt, `recover`, lock, reset guards) - data stayed readable through a passphrase change and a full recovery, and both reset guards fire.
- Confirm the recovery-key-first framing (create a recovery key before you need it; the words are shown once), the passphrase prerequisite, and the recover/rekey command surface are documented.

## Outcome

- Page verified compliant at HEAD; the recovery/rekey/lock surface is documented and confirmed working by the persona. Delta: none required. CLI conformance gate green.

## Notes

- Residual m17 (`<profile-id>` placeholder leak in `config lock`) is an APP-side output finding, out of documentation scope.
