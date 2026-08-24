---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:fa9dc4eefae7994e7b0b4c479972727c6d1d984622f08a5b8241f99973a6353b'
step_id: 'S12'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 303 deadlines, remove every non-owner copy, preserve the 2024 cutover, and materialise every supported monthly and quarterly row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/`

## Description

- Search the code and decision corpora with Vaultspec RAG before editing.
- Reuse `select_revision`, its shared period-token matcher, and the registry ownership validator as the only ownership authorities.
- Remove every already-authored Modelo 303 deadline copy whose containing revision is not the canonical owner.
- Preserve the period-sensitive 2024 boundary: `1T`, `2T`, `01`, and `06` remain early; `3T`, `4T`, and `12` remain late.
- Keep the plan Step open because the shared supported-year catalogue required to prove complete materialisation is not available yet.

## Outcome

The owner-normalisation portion is complete. Existing grounded rows now have exactly one containing revision, selected solely by filing year and canonical period token. No new selector, cadence map, horizon, or deadline resolver was introduced.

Revision `2023` now carries exactly sixteen officially grounded windows: four quarterly and twelve monthly coordinates, one per token in both its period selector and filing schedules. Presentation and direct-debit dates come from the bundled official AEAT 2023 calendar, except the following-January `4T` and `12` coordinates, which come from the bundled official AEAT 2024 calendar. Cold M303 validation passes and the validated authority projects exactly those sixteen rows for filing year 2023.

The Step remains deliberately incomplete because its full acceptance text requires every supported M303 monthly and quarterly row, while the shared supported-year catalogue is not yet available to define that horizon canonically. Current residual sparse coordinates are exact: revision `2022` has only `4T`; the two 2024 owners together lack monthly `02`-`05`, `07`-`11`; revision `2025` lacks monthly `02`-`05`, `07`-`11`; and revision `2026-y-siguientes` lacks monthly `12` for explicitly authored year 2026. Those rows were not derived from cadence arithmetic or extended beyond published evidence.

## Notes

- Vaultspec RAG located the existing `select_revision`, ownership validator, period authority, deadline projection, and tests before editing; the follow-up search found no redeclared selector, resolver, cadence map, or horizon.
- Focused M303 deadline tests passed: 4 tests. Canonical ownership tests passed: 4 tests. The complete M303 registry test module passed: 50 tests. Ruff passed.
- Isolated cold construction through `load_registry_tree` plus `RegistryValidator.validate_modelo` passed with sixteen 2023 windows. Full validated-authority construction also passed once the independently owned M322 repair was present, and projected sixteen M303 rows for 2023.
- Complete periodic materialisation remains deferred to the canonical temporal-coverage catalogue owned by the registry-temporal-coverage campaign; no filing-year horizon was inferred locally.
