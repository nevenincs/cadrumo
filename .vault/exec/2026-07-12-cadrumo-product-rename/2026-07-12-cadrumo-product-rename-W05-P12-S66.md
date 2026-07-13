---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S66'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S66 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update Hungarian product locale messages through the locales CLI and ## Scope

- `Hungarian locale catalogue` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update Hungarian product locale messages through the locales CLI

## Scope

- `Hungarian locale catalogue`

## Description

- Audit the existing Hungarian catalogue WIP by product-versus-authority referent.
- Route every mutation through `python -m cadrumo.locales set hu KEY VALUE` under isolated state roots.
- Rename product commands, settings, storage names, headings, and recovery guidance to Cadrumo.
- Translate ten English-identical leaves into Hungarian to restore the honesty ratchet without allowlisting.

## Outcome

The Hungarian catalogue contains 204 semantic updates and no former product
command or storage identity. The unallowlisted English-identical count is 106,
equal to the unchanged honesty ceiling, so the honesty gate passes. YAML,
locale integrity, locale CLI round-trip, and multiline round-trip checks pass.

## Notes

The audit and scaffold checks retain the campaign's 30 missing keys for S67.
Inter-locale parity is temporarily red because the concurrent Catalan S65 WIP
has one additional key not yet present in English, Spanish, or Hungarian; S66
did not mutate `ca.yml` or any honesty allowlist.
