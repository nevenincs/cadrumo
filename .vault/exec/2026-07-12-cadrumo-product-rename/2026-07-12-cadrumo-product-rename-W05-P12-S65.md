---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S65'
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
     The S65 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update Catalan product locale messages through the locales CLI and ## Scope

- `Catalan locale catalogue` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update Catalan product locale messages through the locales CLI

## Scope

- `Catalan locale catalogue`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Restore the Catalan catalogue byte-for-byte from the committed authority after an external writer introduced lossy encoding damage.
- Rewrite 209 product-owned command, profile, environment, vault, and landing-copy leaves through `cadrumo.locales set` under an isolated Cadrumo state root.
- Preserve AEAT authority, registry taxonomy, legal, portal, session, and evidence terminology.
- Verify every locale CLI mutation with pre/post hashing, YAML parsing, and replacement-character rejection.
- Audit the finished catalogue for rename residue, catalogue drift, translation honesty, and locale coverage.

## Outcome

The Catalan catalogue now names Cadrumo as the product and uses `cadrumo` for operator commands while retaining AEAT wherever it denotes the external tax authority. The intended-key audit reports zero remaining product rename leaves. Catalogue audit reports exactly the 30 shared missing scaffold keys reserved for `W05.P12.S67`, with no extras. Four focused locale honesty and coverage tests pass.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Three external-write incidents occurred during execution. The first exposed transient malformed YAML; the second overwrote early Catalan text through a lossy code page and introduced replacement characters. Work stopped at each safety gate. Recovery used an `apply_patch` reverse patch to reconstruct the catalogue from the current committed blob, after which all intended mutations were replayed exclusively through the locale CLI. A later concurrent scaffold added 30 premature placeholder leaves and restored stale command values. The final recovery removed exactly those 30 leaves and repaired the stale product-command values through the locale CLI. The 30 cross-locale scaffold keys remain deliberately absent for `W05.P12.S67`.
