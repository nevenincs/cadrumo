---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c4a3085ce78a04c379f66ecbd52d83829da6ce1b33afa07dd14919029e955caa'
step_id: 'S37'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

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
