---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-registry-format with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-02-arch-remediation-registry-format-plan placeholders are machine-filled by
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
     The Migrate modelo 231 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator and ## Scope

- `src/aeat/_data/registry/aeat/modelos/231` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate modelo 231 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator

## Scope

- `src/aeat/_data/registry/aeat/modelos/231`

## Description

- Lift the four inline array-table fields (`casillas`, `workbook_parity_refs`, `application_links`, `filing_schedules`) verbatim out of the 231 `2021-y-siguientes` `revision.toml` into per-field fragment files, leaving only scalar metadata inline.

## Files

- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/casillas/0001-casillas.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/workbook_parity_refs/0001-workbook_parity_refs.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/application_links/0001-application_links.toml`
- `src/aeat/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/filing_schedules/0001-filing_schedules.toml`

## Outcome

Behaviour preserved: the compiled-schema equality gate confirms the fragmented `ModeloRevision` is identical to the pre-migration inline shape; the loader directory-mode reviewability/inventory/schema-owned gates and the committed-registry + authority validation suites stay green.

## Notes

Purely mechanical authoring-surface move; no calc content changed.
