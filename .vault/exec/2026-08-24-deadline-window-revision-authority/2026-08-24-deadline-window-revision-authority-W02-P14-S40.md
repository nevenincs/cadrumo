---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c91a388b7d5b85c37f64738b01e00e5df9e3ad19e6c913c90ad22613a3be7729'
step_id: 'S40'
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
     The S40 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Re-adjudicate Modelo 130 deadlines for supported filing years 2022-2026 and materialise all 8 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/130/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-adjudicate Modelo 130 deadlines for supported filing years 2022-2026 and materialise all 8 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/130/`

## Description

- Discover the canonical deadline ownership, period, cadence, supported-year,
  projection, and filing-window resolution authorities with Vaultspec RAG.
- Confirm exact production symbols and the complete Modelo 130 registry surface.
- Transcribe the eight missing 2022 and 2023 quarterly coordinates from bundled
  official AEAT taxpayer calendars without deriving dates.
- Close revision and construct provenance over the 2022-2026 calendar sources and
  all twenty deadline identifiers.
- Replace generic record-design provenance on existing dates with their physical
  presentation-year calendar and remove the unpublished 2027 bank cutoff.
- Add exact census, date, source, construct, canonical-owner, and authority-projection
  regression coverage.

## Outcome

Modelo 130 now declares exactly twenty unique quarterly coordinates: four for each
supported filing year from 2022 through 2026. The eight-row increase is exactly the
measured 2022-2023 gap. Following-January rows cite the calendar for the physical
presentation year. Every published bank-domiciliation cutoff is retained, while the
previously inferred 2027 cutoff is absent.

Vaultspec RAG and exact-symbol confirmation found no selector, resolver, period parser,
cadence authority, supported-year horizon, deadline catalogue, or downstream
deduplication introduced by this step. The data continues to use `select_revision`,
`Period`, `registry_period_kind`, `ValidatedRegistryAuthority.deadline_windows`, the
shared supported-filing-year catalogue, and `resolve_filing_window`.

Focused Ruff and nineteen Modelo 130 registry/engine tests pass, including cold registry
validation and the exact twenty-row authority census.

## Notes

The 2026 fourth-quarter close is stated directly by the bundled official Modelo 130
instructions. No 2027 taxpayer calendar is bundled, so no bank-domiciliation cutoff is
claimed for that row. Unrelated concurrent worktree changes were left untouched.
