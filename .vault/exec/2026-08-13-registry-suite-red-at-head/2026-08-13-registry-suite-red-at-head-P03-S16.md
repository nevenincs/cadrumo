---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:938702f0bcd30fc3812a944a1bf9bd44a4dca2bf9f9277ce3672fd8f2dc7bfe2'
step_id: 'S16'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-suite-red-at-head with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
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
     The Set the missing English help string for the standard-rate repercutido casilla through the locales CLI in all four catalogues and ## Scope

- `src/cadrumo/locales/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Set the missing English help string for the standard-rate repercutido casilla through the locales CLI in all four catalogues

## Scope

- `src/cadrumo/locales/`

## Description

- Resolve the current English M303 standard-rate help projections through the
  production locale authority.
- Run the canonical locale status scan.

## Outcome

Both current projections resolve the same nonblank English help text: `Total
output VAT calculated at the standard 21% rate.` The earlier missing-string
defect was delivered by later locale work.

## Notes

- `python -m dev.locales status` exited zero with no findings.
- Direct and ordered production resolution succeeded for both the 2026 revision
  casilla key and the continuity projection key.
