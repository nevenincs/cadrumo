---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:17162d75dada5a39abf312eae0870d905e483a11b92c459d077788feddd3f6ef'
step_id: 'S12'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Re-adjudicate Modelo 303 deadlines, remove every non-owner copy, preserve the 2024 cutover, and materialise every supported monthly and quarterly row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_registry.py`

## Description

- Search the code and decision corpora with Vaultspec RAG before editing and repeat the redeclaration audit after implementation.
- Reuse `select_revision`, its shared period-token matcher, and the registry ownership validator as the only ownership authorities.
- Preserve the period-sensitive 2024 boundary and materialise only dates and payment cutoffs present in bundled official AEAT calendars.
- Keep the Step open while filing-year 2026 month `12` depends on the unpublished 2027 calendar/payment cutoff.

## Outcome

The canonical M303 historical schedule is now complete for every officially evidenced coordinate in filing years 2022, 2024, and 2025. Exactly 21 formerly missing rows were added: 2022 quarters `1T`-`3T`; 2024 months `02`-`05` and `07`-`11`; and 2025 months `02`-`05` and `07`-`11`. Existing retained rows for those years were re-adjudicated and now carry their exact AEAT calendar presentation dates, direct-debit cutoffs, and applicable calendar source refs.

The 2024 form-layout cutover remains canonical. Revision `2024-hasta-08-y-2t` owns `1T`, `2T`, and months `01`-`08`; revision `2024-desde-09-y-3t` owns `3T`, `4T`, and months `09`-`12`. Ownership is proved through the existing `select_revision` authority, not a local map. Construct membership and source closure now enumerate every new deadline row and calendar source.

The only selector coordinate without an authored filing-year-2026 row is month `12`. It remains deliberately unauthored because its physical filing window and payment cutoff belong to the unpublished 2027 calendar cycle; no date was inferred. Therefore Step `W02.P04.S12` remains unchecked.

## Verification

- Mandatory pre-edit Vaultspec RAG code and vault searches located the existing `select_revision`, ownership validator, deadline projection, period authority, ADR, plan, and prior S12 record.
- Post-edit Vaultspec RAG returned the same canonical authorities and the focused regression only. Exact `rg` confirmation found no selector, resolver, cadence authority, filing-year horizon, enum, or code map declared in the M303 data/test surface.
- Focused M303 validator/deadline tests: `6 passed`.
- Ruff on the focused M303 test module: passed.
- `git diff --check`: passed.

## Review

The focused review found no critical, high, medium, or low implementation issue. It confirmed official-source provenance, exact canonical owner placement, construct/source closure, the 21-row census, and the explicit 2026/12 residual. The review is recorded in the related S12 audit.
