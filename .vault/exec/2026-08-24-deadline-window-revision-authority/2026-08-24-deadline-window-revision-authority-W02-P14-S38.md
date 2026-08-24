---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8e5f0313e059ea1cb5c306c68bb81d6a2c191b84c3d45cbf349681194f28dd97'
step_id: 'S38'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 115 deadlines for supported filing years 2022-2026 and materialise all 16 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/115/`

## Description

- Locate the canonical deadline ownership, semantic-coordinate, cadence, supported-year,
  authority-projection, and filing-window-resolution implementations with Vaultspec RAG.
- Confirm the exact symbols with a targeted sweep before changing only Modelo 115 corpus
  declarations and their discriminating registry regression.
- Transcribe sixteen missing quarterly presentation windows and published bank-domiciliation
  cutoffs from the bundled AEAT taxpayer calendars for physical years 2022 through 2026.
- Close revision and construct provenance over all five calendar sources and all twenty
  deadline identifiers while preserving the existing applicability predicate.
- Validate every supported coordinate through `select_revision` and
  `ValidatedRegistryAuthority.deadline_windows`, then run focused tests and Ruff.

## Outcome

Modelo 115 now owns exactly twenty unique quarterly deadline coordinates: four per
supported filing year from 2022 through 2026. This is the measured four-to-twenty
change, exactly sixteen materialised cells. Following-January closes cite the calendar
for their physical presentation year. Published payment cutoffs are present for every
physical close through 2026; the existing 2026 4T window retains no ungrounded 2027
payment cutoff.

Vaultspec RAG located `_supported_filing_years.audit_supported_filing_years`,
`_temporal.select_revision`, `_deadline_coordinate.deadline_semantic_coordinate`,
`core.registry_period_kind`, `ValidatedRegistryAuthority.deadline_windows`, and
`deadlines.resolve_filing_window` as the existing authorities. Exact-symbol confirmation
found no selector, resolver, parser, cadence authority, supported-year horizon, or
deadline catalogue added to production code. `_SUPPORTED_DEADLINES` is an independent
test oracle only; the shipped declarations remain fragmented registry data consumed by
the existing loader and canonical authority.

Focused verification passed: four Modelo 115 registry/runtime tests, Ruff, and a live
authority census returning `4` ordered quarterly windows for each year 2022-2026.

## Notes

No dates were inferred. The opening day, presentation close, and payment cutoff were
read from the bundled calendar tables. No unrelated dirty or staged paths were touched.
