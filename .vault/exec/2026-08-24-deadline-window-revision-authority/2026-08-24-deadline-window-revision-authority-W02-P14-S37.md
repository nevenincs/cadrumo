---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2e29d7120285828ef03d10486110f0d16da59956076426a43d49ab12149ff80a'
step_id: 'S37'
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
     The S37 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Re-adjudicate Modelo 111 deadlines for supported filing years 2022-2026 and materialise all 48 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/111/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-adjudicate Modelo 111 deadlines for supported filing years 2022-2026 and materialise all 48 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/111/`

## Description

- Locate canonical deadline authorities with Vaultspec RAG and confirm exact symbols.
- Re-adjudicate all monthly and quarterly Modelo 111 coordinates against bundled AEAT calendars.
- Materialise the 48 absent 2022 through 2024 cells and correct shifted presentation dates.
- Preserve presentation and bank-domiciliation cutoffs as separate existing fields.
- Close revision and construct provenance over the official calendar sources.
- Add exact census, date, source, cutoff, ownership, closure, and projection regressions.

## Outcome

- Modelo 111 declares exactly 80 coordinates: 16 in each filing year from 2022 through 2026.
- The measured delta is exact: 32 retained plus 48 materialised.
- All coordinates resolve through `select_revision` to `2019-y-siguientes`; authority projection returns 16 per year.
- Seventy-eight cutoffs are explicitly sourced; `2026 12` and `2026 4T` omit unpublished 2027 payment cutoffs.
- Focused verification passed: 11 tests and focused Ruff.

## Notes

- Semantic queries covered revision ownership, period/cadence/supported-year authority, and source/construct closure.
- Exact confirmation pinned `select_revision`, `Period`, `registry_period_kind`, `deadline_window_semantic_coordinates`, `ValidatedRegistryAuthority.deadline_windows`, and `resolve_filing_window`; none was redeclared.
- Calendar provenance follows the physical close year. The two 2027 closes retain official Modelo 111 instructions because no 2027 calendar is bundled.
- No unrelated working-tree modification was staged or changed.
