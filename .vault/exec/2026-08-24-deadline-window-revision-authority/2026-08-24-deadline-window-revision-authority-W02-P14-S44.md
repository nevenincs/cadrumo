---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:dc2cafee5c04ab52cf5597fbc8b89577aeafa9b6577eb52e2f7c3b846747906e'
step_id: 'S44'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 349 deadlines for supported filing years 2022-2026 and materialise all 32 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/349/`

## Description

- Locate canonical revision, period, cadence, supported-year, semantic-coordinate, projection, and filing-window authorities with Vaultspec RAG.
- Confirm every located authority and Modelo 349 insertion point with exact-symbol searches and whole-file reads.
- Re-adjudicate all 2022 through 2026 monthly and quarterly cells against bundled AEAT contributor calendars and the bundled plazo law.
- Materialise the 32 absent 2022 and 2023 cells beneath the one canonically selected revision.
- Correct retained 2024 through 2026 nominal-day closes to the dates published by AEAT.
- Close revision and construct provenance over the five official calendar sources.
- Add exact census, date, source, ownership, construct-closure, and authority-projection regressions.

## Outcome

Modelo 349 now declares all 80 monthly and quarterly deadline coordinates for supported filing years 2022-2026. The final 2026 `12` and `4T` rows are owned by revision `2020-y-siguientes`, open 2027-01-01, and close 2027-02-01. Orden EHA/769/2010 article 10 supplies the thirty-natural-day January rule for both coordinates; the general next-working-day rule moves the Saturday terminal day to Monday.

Monthly and quarterly schedule selection remains unchanged, every coordinate resolves through `select_revision`, and construct/source closure is exact. No 2027 calendar row, deadline calculator, or modelo-specific resolver was invented. The focused repaired-model and deadline-engine run passes 164 tests. Step `W02.P14.S44` is complete.

## Notes

Vaultspec RAG and exact confirmation found and reused `select_revision`, `Period`, `registry_period_kind`, `deadline_window_semantic_coordinates`, the shared supported-filing-year catalogue, `ValidatedRegistryAuthority.deadline_windows`, and `resolve_filing_window`. No revision selector, filing-window resolver, period parser, cadence authority, supported-year horizon, deadline catalogue, or downstream deduplicator was added or redeclared.
