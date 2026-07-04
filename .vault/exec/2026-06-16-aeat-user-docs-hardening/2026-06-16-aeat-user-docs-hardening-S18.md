---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S18'
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
     The S18 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden modelo-036.md and ## Scope

- `docs/how-to/modelo-036.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden modelo-036.md

## Scope

- `docs/how-to/modelo-036.md`

## Description

- Verify-close: read `modelo-036.md` against its 2026-06-18-audit assessment and confirm resolution at HEAD.
- Confirm the audit's own positive verdict for this page: `modelo-036` is the cleanest command surface (Doc 4/5, App 5/5, 0 major). The alta/modificación/baja, list, view-by-id-and-prefix, no-match refusal, idempotency, and `--note-only` flows are all delivered exactly as documented, with graceful and instructive refusals.
- Confirm the record-a-036-you-filed-at-AEAT framing (the tool records the census declaration you filed; it never submits to AEAT) is stated.

## Outcome

- Page verified compliant at HEAD; the audit records `modelo-036` as clean with no major findings. Delta: none required. CLI conformance gate green.

## Notes

- The cleanest surface in the audit; verify-close confirms it holds at HEAD.
