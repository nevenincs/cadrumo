---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S04'
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
     The S04 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden choose-modelo.md and ## Scope

- `docs/how-to/choose-modelo.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden choose-modelo.md

## Scope

- `docs/how-to/choose-modelo.md`

## Description

- Verify-close: read `choose-modelo.md` in full against the aeat-user-docs-hardening + aeat-documentation-workflow standard and confirm the page's audit findings are resolved at HEAD.
- Confirm finding M7 (overview explain vs profile preflight read as a contradiction): the page now explains the distinction on-page - applicability facts vs filing-context facts - so a `ready` preflight is not sold as an applicability confirmation.
- Confirm finding m8 (domain enumeration incomplete): the domain list now includes `cross_tax`, `irnr`, `patrimonio`, and `iae`, and the `modelo describe` structure counts are documented.
- Confirm every documented `aeat ...` command resolves against the live CLI (conformance gate).

## Outcome

- Page verified compliant at HEAD; audit findings M7 and m8 resolved (via the 2026-06-19 documentation batch). Delta: none required this pass.
- Voice is imperative, taxpayer-general (NIF/CIF/DNI/NIE), story-driven with resolving cross-links; no first-person-plural, gerund-header, or self-praise anti-patterns.

## Notes

- CLI conformance gate green (58 passed) across the how-to surface. No page edit needed.
