---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S14'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Register locale keys for the parity panic error and the coverage advisory via the locales CLI and ## Scope

- `src/aeat/locales/en.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Register locale keys for the parity panic error and the coverage advisory via the locales CLI

## Scope

- `src/aeat/locales/en.yml`

## Description

- The coverage advisory message follows the existing modelo-export notice convention: a constant English message (`_COMPLETENESS_UNVERIFIED_MESSAGE`) on the result plus a notice `code` (`modelo.export.completeness_unverified`) as the translation key.

## Outcome

No locale-CLI keys were added: the entire modelo-export notice family (e.g. `_local_export_evidence_notice`) uses constant messages and the notice `code` as the translation anchor, and its sibling code is not registered in the locale catalogues either. Adding a locale key for only this notice would be inconsistent with the family.

## Notes

Deliberate deviation from the plan Step's "add locale keys" wording, to match the established export-notice convention rather than introduce a lone localized notice. If the export-notice family is later locale-routed, this notice joins it in the same change.
