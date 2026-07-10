---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S20'
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
     The S20 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden modelo-390.md and ## Scope

- `docs/how-to/modelo-390.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden modelo-390.md

## Scope

- `docs/how-to/modelo-390.md`

## Description

- Verify-close: read `modelo-390.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M15 (303->390 dependency had no on-page on-ramp + wrong framing; 303 bindings called `previous_filing` on the page but the CLI reports `relation_prefill`): the page now documents the filed-303-evidence requirement, prepares the same year's Modelo 303 periods first, and names the 303-derived values' binding source correctly.
- Confirm finding M16 (`live iva-wallet pull-history` failed as written): the documented form now carries its required `--from-year`/`--to-year`.

## Outcome

- Page verified compliant at HEAD; findings M15 and M16 resolved (2026-06-19 documentation batch). Delta: none required. CLI conformance gate green.

## Notes

- The 390 honestly documents that its review depends on the same year's periodic 303 values and the establishment paths.
