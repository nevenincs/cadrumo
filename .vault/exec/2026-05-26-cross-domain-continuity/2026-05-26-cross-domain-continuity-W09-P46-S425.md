---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S425'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Add real cross-path period-date regressions covering every contiguous token, Modelo 202 1P/2P/3P calculation-to-draft-replay parity, and Sheets pull/reference parity against the normal calculation path

## Scope

- `src/aeat/domain/tests/test_period.py`
- `src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py`
- `src/aeat/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py`
- Existing S432 `src/aeat/adapters/outbound/google/tests/test_pull_adapter_helpers.py` stale-layout coverage

## Description

- Ground the test matrix with `vaultspec-rag`, the W09.P46 plan row, cross-domain reference, S424 and S432 records, the current audit findings, and the full existing real-behavior test helpers.
- Assert all contiguous registry tokens use the typed `Period` end through the core range helpers and `calculation_filing_date`; assert `4P`, `AD-HOC`, and concrete `EVENT-N` codes retain the explicit 31 December calculation fallback while both strict range helpers refuse them.
- Calculate each Modelo 202 Manual-practical 2025 instalment in its encrypted work-unit lifecycle, rehydrate persisted filing replay inputs, assert filing's actual `_filing_period_date` selects April, October, and December respectively, and compare the rebuilt draft's casilla `03` against the calculated revision.
- Build committed Modelo 369 exterior export plans for every `EXT-1T` through `EXT-4T` period, mechanically project their real plan cells into typed pull records, and compare `compute_from_pull` with the normal registry calculation at the corresponding statutory quarter end.
- Pin the exterior reference-date boundary with committed Modelo 369 `EXT-1T` for 2021: its 31 March calculation anchor rejects the revision that began on 1 July, while the positive legacy 31 December control selects `esquema-exterior` and proves the avoided drift.
- Retain S432's real current/pre-change `calc-sheets` engine-stamp acceptance and refusal cases as the layout-compatibility proof before any coordinate read.

## Outcome

The cross-path matrix now provides concrete real-behavior regression evidence for core period semantics, filing replay, normal calculation, Sheets export/pull recomputation, and the exterior workbook compatibility boundary. A review found and corrected two initially date-insensitive assertions: Modelo 202 now calls the filing route directly, and the Modelo 369 reference selection now observes the exterior revision's effective date. No fake, mock, stub, patch, or monkeypatch is used.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/tests/test_period.py src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py src/aeat/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py`
- `uv run --no-sync pytest src/aeat/domain/tests/test_period.py src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py src/aeat/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google/tests/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/tests/test_compute_from_pull.py -q` — 71 passed.
- Scoped `git diff --check` — clean apart from Git's informational CRLF conversion notices for pre-existing working-tree files.

## Notes

The Modelo 369 exterior binding is source-owned `ledger_oss_aggregation`; the committed no-ledger plan/pull parity control correctly remains zero-valued instead of accepting a fabricated caller binding. The date-effective committed-reference boundary and S432's version gate make the exterior anchor and stale-layout disposition observable without bypassing that ownership. The S425 plan checkbox is intentionally unchanged pending independent review.
