---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S63'
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
     The S63 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update English product locale messages through the locales CLI and ## Scope

- `English locale catalogue` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update English product locale messages through the locales CLI

## Scope

- `English locale catalogue`

## Description

- Audit the existing English WIP by referent before adoption.
- Mutate every English catalogue leaf through `python -m cadrumo.locales set en KEY VALUE` under isolated local storage.
- Rename standalone product and command references to Cadrumo and `cadrumo`, including local-profile and secret-store copy.
- Preserve AEAT for the agency, Sede, legal corpus, portals, filing, and official evidence, plus internal `aeat_*` taxonomy and provenance identifiers.
- Leave the thirty missing cross-code keys untouched for S67.

## Outcome

The English catalogue now presents the canonical Cadrumo product and command
identity without rewriting Spanish tax-authority or internal contract referents.

## Notes

- The locale CLI updated the catalogue key-by-key; no YAML or allowlist mutation was hand-written.
- YAML parsing, eight focused locale coverage/positional/CLI tests, residue checks, and diff checks passed.
- Locale audit reports the same thirty missing code keys in every locale; S63 did not scaffold them because S67 owns cross-code completeness.
- The translation-honesty suite has one pre-existing cross-locale ratchet failure: Hungarian currently has 114 values identical to English against a ceiling of 106. S63 does not edit Hungarian or its allowlist.
- Formal review found four Unicode replacement characters introduced at the shell-to-CLI boundary; the affected leaves were restored through the locale CLI and the follow-up Unicode scan passed.
