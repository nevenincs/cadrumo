---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:306cf4c17bcca378a93aeef2857ff3cc060cb3c2eed2e8865bd050baacb0ff12'
step_id: 'S424'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Introduce one typed calculation filing-date resolver for Period and route verification, filing replay, Sheets pull/parity, and formula-runtime fallback through it

## Scope

- `retain the sanctioned Modelo 202 instalment mapping and define the existing non-span fallback explicitly`
- `src/aeat/domain/period.py src/aeat/application/verification/ src/aeat/application/filing/ src/aeat/adapters/outbound/google/ src/aeat/application/storage/calc_sheets/ src/aeat/domain/calculations/registry/`

## Description

- Ground the period-date convergence in semantic code and vault searches, then read the live period, verification, filing, formula-runtime, calculation-preparation, Sheets export, parity, and pull implementations in full.
- Add `calculation_filing_date(period)` as the typed calculation-context authority. It returns the contiguous period end, derives an `EXT-nT` period's corresponding ordinary quarter end, preserves Modelo 202 `1P` through `3P` payment-month ends, and uses the explicit 31 December policy for `4P`, `AD-HOC`, and `EVENT-N`.
- Preserve `period_start_date` and `period_end_date` as strict range helpers; they continue to refuse exterior, instalment-without-sanctioned-mapping, ad-hoc, and event non-span codes.
- Route declaration verification, filing draft replay, formula-runtime defaults with a constructible filing period, normal calculation preparation, filed-state verification, and work-unit taxation replay through the new resolver.
- Route the calculation-sheet export compiler, local parity runtime and seed layout, and Google Sheets pull layout and compute replay through the same anchor without changing the existing `calc-sheets/0.2.0` compatibility boundary.

## Outcome

Every S424 calculation context now selects one filing date from the typed `Period` instead of maintaining separate monthly, exterior-period, instalment, or year-end fallbacks. The live direct probe confirmed the contiguous month end, all required exterior and Modelo 202 mappings, residual non-span fallback, and unchanged strict-helper refusals.

Validation passed:

- `uv run --no-sync ruff check` on the ten S424-owned production modules.
- `uv run --no-sync pytest src/aeat/domain/tests/test_period.py src/aeat/application/filing/tests/test_build_draft_identity.py src/aeat/application/storage/calc_sheets/tests src/aeat/adapters/outbound/google/tests/test_compute_from_pull.py src/aeat/adapters/outbound/google/tests/test_pull_adapter_helpers.py -q` — 127 passed.
- Scoped `git diff --check` — clean apart from Git's informational CRLF conversion notices for pre-existing working-tree files.

## Notes

The broader focused run including `src/aeat/application/verification/tests/test_verify.py` had 79 passes and one failure unrelated to S424: a concurrent Modelo 100 profile-binding change now requires `renta-2025-profile-has-economic-activity` in that test's pre-existing direct-runtime fixture. The S424 period-date code does not touch that binding or Modelo 100's annual anchor. No S425 cross-path regression tests were added; this record remains pending independent review and the plan row is intentionally unchecked.
