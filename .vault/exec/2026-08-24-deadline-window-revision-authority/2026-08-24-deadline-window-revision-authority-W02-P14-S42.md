---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7728a623f52316ee56f5993fd3b01c345574771c1c52590aeb9d341c119e50e0'
step_id: 'S42'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S42 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Re-adjudicate Modelo 202 deadlines for supported filing years 2022-2026 and materialise all 9 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/202/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-adjudicate Modelo 202 deadlines for supported filing years 2022-2026 and materialise all 9 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/202/`

## Description

- Lead discovery with Vaultspec RAG, read the complete M202 revision surfaces, and confirm canonical authorities with exact-symbol searches.
- Extract the bundled official AEAT 2022-2024 contributor calendars and transcribe only their published M202/M222 filing and direct-debit dates.
- Materialise the nine measured 2022-2024 `1P`/`2P`/`3P` windows in their `select_revision` owners.
- Close revision, construct, source, and deadline-application-link provenance for all supported 2022-2026 M202 windows.
- Add exact census, date, source, typed-period, and canonical-owner regressions.
- Run focused registry validation, ownership/identity tests, Ruff, Vaultspec checks, and an isolated architecture review.

## Outcome

Modelo 202 now has exactly fifteen supported-year deadline coordinates: three canonical instalment periods for each filing year from 2022 through 2026. The nine previously missing coordinates are grounded in the bundled official calendars; all fifteen rows carry their year-specific calendar citation and resolve to their containing revision through `select_revision`.

No selector, resolver, period parser, cadence mapping, supported-year horizon, or deadline catalogue was introduced. The data and tests consume the existing `Period`, `registry_period_kind`, `PeriodKind`, and `select_revision` authorities.

## Notes

The earlier family dispositions incorrectly stated that the 2022 calendar was absent; the official PDF was already bundled and readable. Those dispositions were removed when their families became populated. The schema-level deadline `period_kind` remains `quarterly`, while canonical token classification correctly reports `PeriodKind.INSTALMENT`; this preserves the existing deadline schema and avoids creating a second cadence vocabulary.
