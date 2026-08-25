---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e4ed5cae235844497c68903740ccce7076cc654b11d00eb28ac7a6532c50639b'
step_id: 'S15'
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
     The S15 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
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
     The Narrow the Modelo 720 revision 2013-y-siguientes claimed filing years to those its declared layout design covers, or declare the design that covers 2012 and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/720/revisions/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Narrow the Modelo 720 revision 2013-y-siguientes claimed filing years to those its declared layout design covers, or declare the design that covers 2012

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/720/revisions/`

## Description

- Trace the current Modelo 720 source authority and revision selector.
- Verify filing year 2012 resolves to the declared 2013 design revision through
  the production registry authority.

## Outcome

The current source authority explicitly records a 2013 record-design epoch whose
first presentation covers ejercicio 2012. The revision therefore truthfully
starts at filing year 2012 without inventing a separate 2012 layout.

## Notes

- `test_committed_modelo_720_resolves_revision_by_filing_year`: 3 passed.
- The 2012 case resolves `2013-y-siguientes` under
  `orden-hap-72-2013:art-1`.
