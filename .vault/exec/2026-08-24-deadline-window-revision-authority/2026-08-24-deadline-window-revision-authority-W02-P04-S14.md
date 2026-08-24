---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:23f098bf9d399f548688a66b109e10911cfb9327cf6ee028bf55ce6c0da7ba84'
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

The canonical 2008-2025 owner now contains exactly twelve deadlines for each supported filing year 2022 through 2025. The 36 added historical rows preserve the taxpayer calendars' shifted presentation dates and include payment cutoffs only because AEAT's domiciliation tables explicitly group monthly Modelos 303 and 353. Following-January rows cite the calendar publishing their physical dates. The 2026 owner retains exactly periods 01 through 11.

This Step remains open. Period 12 of filing year 2026 cannot be authored from the available 2026 calendar because its physical filing window and domiciliation cutoff occur in 2027; no official 2027 taxpayer calendar is bundled or published in the adjudicated authority. The plan checkbox remains unchecked rather than weakening the no-inference rule.

## Notes

Vaultspec RAG semantic discovery returned the nearest exact ownership/projection analogue in `test_modelo_322_registry.py`, the validator authority in `test_deadline_window_ownership.py`, and the accepted deadline ADR, research, and plan. The TOML-specific query returned no production-code result because registry data files are not indexed as source-code chunks; whole-file reads and exact `rg` confirmation then pinned both M353 deadline fragments and `select_revision`. No resolver, selector, cadence authority, period parser, deadline catalogue, or code map was introduced.

Ruff and diff hygiene pass for the owned files. Direct canonical-loader evidence proves 48 rows in 2008-2025 and 11 rows in 2026-y-siguientes. The focused fleet-backed module is currently blocked before any M353 assertion by unrelated concurrent invalid M303 and M390 revisions; those failures are recorded without being misreported as M353 failures.
