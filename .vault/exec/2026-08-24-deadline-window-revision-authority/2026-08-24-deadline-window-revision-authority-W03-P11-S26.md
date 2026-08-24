---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a4b7db38483189bc70f354a55e28d7218878b17b466d9efba8f726acfc12d25b'
step_id: 'S26'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Keep DeadlineEngine.compute thin and prove exact-one complete monthly and quarterly emission without local selection or deduplication

## Scope

- `src/cadrumo/domain/deadlines/_engine.py`
- `src/cadrumo/domain/deadlines/tests/test_engine.py`

## Description

- Trace deadline projection semantically with Vaultspec RAG and confirm exact symbols.
- Keep `DeadlineEngine.compute` as a one-for-one consumer of canonical authority rows.
- Exclude resultado/tipo-renta-qualified windows from the pre-calculation schedule and retain their existing post-calculation resolver ownership.
- Prove exact M303 2025 quarterly and REDEME monthly emission.
- Prove every applicable authored periodic authority coordinate is emitted exactly once across filing years 2022-2026.
- Align the M349 2026 regression with the explicitly grounded three-quarter and eleven-month corpus boundary.
- Run focused Ruff and deadline-engine tests and complete an independent focused review.

## Outcome

`DeadlineEngine.compute` remains thin over `ValidatedRegistryAuthority.deadline_windows`:
it contains no revision selection, runtime deduplication, period parsing, or cadence
generation. The audit exposed and repaired four indistinguishable qualified M210 `0A`
obligations in 2025 and 2026. Those windows require calculation resultado and declared
tipo-renta context, so the pre-calculation profile schedule now declines them while the
already implemented canonical post-calculation plazo resolver and typed Notice channel
remain their sole projection path.

An ordinary M303 profile emits exactly `1T`, `2T`, `3T`, and `4T` for 2025. A REDEME
profile emits exactly months `01` through `12`. The fleet regression compares engine
output against every applicable currently authored monthly/quarterly authority row for
both profiles across 2022-2026 through the shared semantic-coordinate constructor and
proves multiplicity one.

Focused verification passed: Ruff reported no findings and the complete engine test
module passed 49 tests. Independent re-review found one HIGH test-oracle weakness and
one MEDIUM locally redeclared supported-year horizon, so this Step remains open pending
their correction even though the production boundary itself was approved.

The remediation replaces that private-helper oracle with an independent expectation
derived from `ValidatedRegistryAuthority.deadline_windows`,
`applicable_filing_schedules`, and `evaluate_profile_conditions`. It consumes
`authority.catalogues.supported_filing_years.years`, so the regression carries no local
year horizon. Exact `Counter` equality now compares all applicable authored periodic
coordinates with emitted periodic coordinates, and an explicit mutation control proves
the gate rejects both a dropped applicable row and a duplicate row. The exact M303 2025
four-quarter/twelve-month assertions and the qualified-M210 exclusion remain intact.

Remediation verification passed Ruff format, Ruff check, and all 42 tests in the full
deadline-engine test module. S26 closes only after the independent remediation review
records APPROVE.

## Notes

The registry corpus still has exactly five deliberately unauthored filing-year-2026
cells whose physical deadlines require the unpublished 2027 taxpayer calendar: M303
month `12`, M322 month `12`, M353 month `12`, and M349 month `12` plus quarter `4T`.
S26 must prove one-for-one emission of the canonical rows the validated authority can
currently project without adding inferred future dates. The fleet completeness gate
remains responsible for closing those corpus cells when authoritative evidence is
enrolled.

The original fleet regression derived expected applicability through the same private
`_obligation_for_window` helper used by `compute`, so an erroneous helper exclusion
could disappear from both sides. It also hard-coded 2022-2026 instead of consuming the
shared supported-year authority. Both findings are now remediated through the public
registry authorities named above; the original findings remain recorded here for audit
continuity.
