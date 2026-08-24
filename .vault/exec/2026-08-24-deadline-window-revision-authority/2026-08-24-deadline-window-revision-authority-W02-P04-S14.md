---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a0832412364cfe6b5f073039fb53c06f29d3cab9616345937c4d9b5e9cdd872b'
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
- Materialise all twelve ejercicio-2025 monthly coordinates beneath `2008-2025` and the eleven ejercicio-2026 coordinates the published table supports beneath `2026-y-siguientes`.
- Preserve the absent ejercicio-2026 December coordinate until the following-year official calendar publishes its exact presentation and payment dates.
- Prove exact date, source, canonical ownership, and authority-projection behavior for every authored 2025 and 2026 coordinate.

## Outcome

The canonical 2025 owner now contains exactly one deadline for each selected monthly period, including the following-January presentation and domiciliation dates published in AEAT's 2026 table. The canonical 2026 owner now contains exactly one deadline for periods `01` through `11`, with presentation and payment dates matching the official 2026 table. No stale 2025 copy remains in the 2026 revision.

This Step remains open. Period `12` of filing year 2026 cannot be authored from the available 2026 calendar because its physical filing window and domiciliation cutoff occur in 2027; no official 2027 taxpayer calendar is bundled or published in the adjudicated authority. The broader 2008-2024 schedule likewise remains outside this Step's authored evidence until the shared supported-filing-years catalogue identifies those years and their evidence requirements.

## Notes

Vaultspec RAG semantic discovery returned the nearest exact ownership/projection analogue in `test_modelo_322_registry.py`, the validator authority in `test_deadline_window_ownership.py`, and the accepted deadline ADR, research, and plan. The TOML-specific query returned no production-code result because registry data files are not indexed as source-code chunks; whole-file reads and exact `rg` confirmation then pinned both M353 deadline fragments and `select_revision`. No resolver, selector, cadence authority, period parser, deadline catalogue, or code map was introduced.

Ruff passed on the changed Python test. Both deadline TOML fragments parse under the standard-library TOML reader and contain exactly twelve and eleven unique ordered periods. A focused module run collected successfully and passed twelve tests; it exposed missing construct citation closure, which was corrected by enrolling all authored deadline IDs and calendar sources. Three authority-wide cases then encountered the shared environment's partially installed PDF dependency. A subsequent rerun was blocked before collection when another shared-environment dependency disappeared, so the corrected construct closure was not claimed as a final green pytest run.
