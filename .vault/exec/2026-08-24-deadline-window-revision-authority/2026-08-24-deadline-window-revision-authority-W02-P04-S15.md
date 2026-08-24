---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:de1495668c29d21424144144792d01a523546244b1b3f0404b6abf602188baba'
step_id: 'S15'
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
     The S15 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Re-adjudicate Modelo 369 deadlines and materialise every supported periodic row without modelo-specific cadence logic and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/369/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-adjudicate Modelo 369 deadlines and materialise every supported periodic row without modelo-specific cadence logic

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/369/`

## Description

- Lead discovery with Vaultspec RAG and confirm every located production symbol with an exact `rg` sweep before editing.
- Re-adjudicate all three Modelo 369 scheme revisions against HAC/610/2021 article 3, the EU VAT Directive OSS/IOSS return articles, and AEAT's explicit non-working-day rule.
- Materialise all missing 2025 import-scheme months and all missing 2026 exterior, union, and import-scheme periods under their existing canonical revision owners.
- Extend each existing construct membership list to close over the newly materialised registry rows.
- Add fleet-facing tests for exact coordinates, dates, provenance, canonical ownership, weekend month ends, and the supported-year boundary.

## Outcome

Modelo 369 now projects exactly twenty canonical deadline windows for each of filing years 2025 and 2026: four `EXT-*` exterior quarters, four union quarters, and twelve import-scheme months. Every window opens on the first and closes on the last calendar day of the natural month following its return period. This includes Saturday and Sunday month ends because AEAT expressly states that Modelo 369 deadlines are not extended when the last day is non-working.

No new cadence calculator, deadline resolver, period parser, revision selector, or source catalogue was introduced. The data continues to consume `Period`, each revision's existing `period_selector`, `select_revision`, `ValidatedRegistryAuthority.deadline_windows`, and the existing HAC/610/2021 legal/source catalogue entries.

Verification passed: the full Modelo 369 registry module (`23 passed`), deadline semantic-coordinate and ownership modules (`9 passed`), Ruff, diff whitespace validation, cold bundled-authority construction, and exact authority counts of `12 + 4 + 4 = 20` for both years.

## Notes

The first focused test run correctly exposed stale construct membership after the deadline rows were added. The three existing construct lists were extended and the complete module then passed. No 2027 filing-year rows were authored; dates in January 2027 are physical filing dates for 2026 Q4/month 12 and retain filing-year identity 2026.

Modified files are the three scheme deadline fragments, their three existing construct fragments, `test_modelo_369_registry.py`, this Step record, the S15 RAG audit, the plan state, and the generated feature index.
