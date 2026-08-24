---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:39a4712d445c4d74b7a48148bb964055c2389963660f6a1e975012ad28c48ac2'
step_id: 'S40'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

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
