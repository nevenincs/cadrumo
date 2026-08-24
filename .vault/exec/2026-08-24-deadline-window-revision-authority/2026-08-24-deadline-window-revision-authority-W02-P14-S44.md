---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ef2cc7ef67fb9e3d47a23c87857aaac1c962de2d3a3ca8ce64b827565d39aeef'
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

- Modelo 349 now declares 78 source-grounded deadline coordinates. The 2022-2025 years each declare all 16 monthly and quarterly coordinates; 2026 declares 14.
- The measured materialisation remains exact: 32 absent 2022 and 2023 coordinates were added. Two pre-existing 2026 coordinates (`12` and `4T`) were removed during review because their physical `2027-01-30` close was not supported by a bundled 2027 AEAT calendar.
- The canonical cadence census retains an explicit two-cell residual for 2026 `12` and `4T`; those cells remain undeclared until official 2027 calendar evidence is bundled and adjudicated.
- Monthly and quarterly profile schedules remain distinct and unchanged; every cell is owned by revision `2020-y-siguientes` through `select_revision`.
- Published weekend and holiday shifts are preserved rather than replaced by nominal day 20.
- Calendar provenance follows the physical close year; no operator-visible 2027 close is inferred from the statutory nominal rule.
- S44 remains open because the two-cell evidence gap prevents complete 2022-2026 materialisation.

## Notes

- Vaultspec RAG and exact confirmation found and reused `select_revision`, `Period`, `registry_period_kind`, `deadline_window_semantic_coordinates`, the shared supported-filing-year catalogue, `ValidatedRegistryAuthority.deadline_windows`, and `resolve_filing_window`.
- No revision selector, filing-window resolver, period parser, cadence authority, supported-year horizon, or deadline catalogue was added or redeclared.
- Commit `32977aebf8` also contains unrelated filing-capability history. That is a historical non-atomic scope defect, not a code-authority defect; this remediation does not rewrite or revert peer-owned history.
- The grounded data and partial census remain useful, but this record does not claim S44 closure.
