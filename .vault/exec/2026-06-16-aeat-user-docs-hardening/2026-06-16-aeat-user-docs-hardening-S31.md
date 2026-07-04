---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S31'
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
     The S31 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden troubleshooting.md and ## Scope

- `docs/how-to/troubleshooting.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden troubleshooting.md

## Scope

- `docs/how-to/troubleshooting.md`

## Description

- Verify-close: read `troubleshooting.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding B4 (`ledger participation rebuild` uninvokable - the optional positional swallowed the `rebuild` token): the callback now dispatches the reserved subcommand token, so `aeat app ledger participation rebuild` runs; the page documents it as the participation-index regenerate path.
- Confirm finding M25 (the page quoted a friendly `ledger preflight` "needs a year" message the command never emits): the page now documents that `ledger preflight` takes an AEAT token AND requires `--year` - and instructs the reader to add `--year` even though the calculate-block error omits it - and shows the real `Missing option '--year'` refusal.

## Outcome

- Page verified compliant at HEAD; findings B4 and M25 resolved (B4 app fix + participation-cli surface test; M25 documented honestly). Delta: none required. CLI conformance gate green.

## Notes

- Residual m16 (invalid-PDF parser-internals leak) and the bucket-session inconsistency are APP-side findings, out of documentation-hardening scope; the doc quotes the real messages.
