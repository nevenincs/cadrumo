---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d2cd0ec193dc349653170e43b31cfcb1b3afb1c0a9e88ef5e79ebebf0acdb709'
step_id: 'S14'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 353 deadlines, remove stale 2025 copies, and materialise every supported periodic row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/353/`

## Description

- Discover the existing deadline-data and ownership patterns through Vaultspec RAG before editing.
- Re-adjudicate Modelo 353 filing and domiciliation dates against the bundled official AEAT 2025 calendar and official 2026 domiciliation table.
- Re-adjudicate all 36 historical filing and domiciliation dates for ejercicios 2022-2024 against the bundled official AEAT taxpayer calendars.
- Materialise those rows beneath the canonical 2008-2025 owner and enroll their sources and identifiers in revision and construct closure.
- Materialise all twelve ejercicio-2025 monthly coordinates beneath `2008-2025` and the eleven ejercicio-2026 coordinates the published table supports beneath `2026-y-siguientes`.
- Preserve the absent ejercicio-2026 December coordinate until the following-year official calendar publishes its exact presentation and payment dates.
- Prove exact date, source, canonical ownership, and authority-projection behavior for every authored 2025 and 2026 coordinate.

## Outcome

Modelo 353 now has all twelve monthly deadline coordinates for every supported filing year 2022-2026. The final `(2026, "12")` coordinate is authored beneath `2026-y-siguientes`, opens 2027-01-01, closes 2027-02-01, and carries the 2027-01-27 payment cutoff through the official M303 procedure's explicit M322/M353 deadline parity and M353's governing legal source.

All 60 supported coordinates have one canonical owner, exact source/construct closure, and authority projection parity. The focused repaired-model and deadline-engine run passes 164 tests. Step `W02.P04.S14` is complete.

## Notes

Vaultspec RAG and exact searches confirm reuse of `select_revision`, `registry_period_kind`, `ValidatedRegistryAuthority.deadline_windows`, and the existing filing schedules. No M353-specific resolver, selector, period parser, cadence authority, horizon, or deadline catalogue was introduced. Ruff and the 164-test focused feature fleet are green.
