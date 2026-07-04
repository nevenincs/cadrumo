---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S17'
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
     The S17 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden ledger-evidence.md and ## Scope

- `docs/how-to/ledger-evidence.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden ledger-evidence.md

## Scope

- `docs/how-to/ledger-evidence.md`

## Description

- Verify-close: read `ledger-evidence.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M17 (`invoice add` -> `link --invoice-id` broken; `--attachment-id` source undocumented): the invoice catalogue-create flow was added so the linkable invoice path works end to end; the page now documents the `--attachment-id` limitation HONESTLY - no operator command currently surfaces the 64-character attachment id, so it directs the reader to `--purchase-invoice-evidence-id` or `doclink` instead until one does.
- Confirm the evidence-bytes-not-links invariant is documented: Drive doclink fetches and encrypts the bytes; Gmail links, arbitrary URLs, and out-of-scope Drive files are refused with an actionable message.

## Outcome

- Page verified compliant at HEAD; finding M17 resolved (catalogue-create landed 7208bb3f0; the residual attachment-id gap is documented honestly rather than papered over). Delta: none required.

## Notes

- The honest "no command surfaces the attachment id yet" note is the correct treatment of a real current-state limitation, not a doc defect. CLI conformance gate green.
