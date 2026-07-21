---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S432'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Version or explicitly invalidate calculation-sheet layouts whose filing-date policy changes, then prove EXT-period export-plan and pull layout parity so a pre-change workbook cannot be read under shifted coordinates

## Scope

- `src/aeat/application/storage/calc_sheets/ src/aeat/adapters/outbound/google/ src/aeat/**/tests/`

## Description

- Ground the compatibility boundary in the live calc-sheets export engine, pull adapter, and the Modelo 369 exterior-period registry surface.
- Publish `CALC_SHEETS_ENGINE_VERSION` and advance the layout stamp from `calc-sheets/0.1.0` to `calc-sheets/0.2.0`.
- Bind metadata classification and the shared read/compute guard to the live layout stamp alongside the existing modelo, revision, period, and registry-SHA identities.
- Invoke the guard immediately after developer-metadata readback, before `plan_layout` or a Sheets value-range request can derive coordinates.
- Add real-registry Modelo 369 `EXT-1T` tests proving a pre-change stamp is refused and an export stamped by the live engine is accepted; add the direct compute defense against a forged matching verdict.

## Outcome

The code-version compatibility boundary is implemented, but S432 remains open pending independent review. A workbook exported under `calc-sheets/0.1.0` now fails before the pull adapter derives any live coordinates; a fresh Modelo 369 exterior-period export carries `calc-sheets/0.2.0` and passes the same guard. The filing-date resolver policy itself remains deliberately untouched.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_engine.py src/aeat/application/storage/calc_sheets/__init__.py src/aeat/adapters/outbound/google/_calc_sheets_pull.py src/aeat/adapters/outbound/google/tests/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/tests/test_compute_from_pull.py src/aeat/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/tests/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/tests/test_compute_from_pull.py src/aeat/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py` — 34 passed.
- Scoped `git diff --check` — clean apart from Git's informational CRLF conversion notices for existing test-file line endings.

## Notes

No date-selection behavior changed in this step. The version bump proactively invalidates layouts emitted by the preceding compiler; the subsequent filing-date resolver work can therefore change exterior-period layout selection without reading old coordinates through the new policy.
