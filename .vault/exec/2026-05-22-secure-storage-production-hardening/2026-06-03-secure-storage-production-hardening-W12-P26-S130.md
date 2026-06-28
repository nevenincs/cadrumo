---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S130'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s130-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S130`

Closed `AFR-028` for the Google calc-sheets pull adapter.

## Description

- Reviewed `src/aeat/adapters/outbound/google/_calc_sheets_pull.py` against the `remote-provider` scanner signal.
- Classified the adapter as a gated Google Sheets readback boundary, not a local persistence implementation.
- Verified Drive ownership and registry metadata gates prevent untrusted or stale workbooks from being consumed by local compute.
- Verified the reviewed module has no naked environment reads or local file read/write paths.
- Recorded the S130 review and updated the affected-file register row to `closed`.

## Outcome

`AFR-028` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google/test_calc_sheets_apply.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_calc_sheets_pull.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google/test_calc_sheets_apply.py`

## Notes

Continuation live review found repeated developer metadata on the configured workbook. `_calc_sheets_pull.py` now refuses conflicting duplicate workbook identity metadata instead of collapsing it by Google API return order, while tolerating repeated `aeat_exported_at` values for the same registry slice. The new refusal is an `OutboundStorageConflictError` with a translated-message key and `tr()`-resolved remediation text.

Follow-up review also found unlocalized blank-id, foreign-ownership, and metadata/snapshot compute refusals. Those paths now carry translated-message keys, and the operator remediation strings resolve through `tr()` where present.

The 2026-06-03 modelo export evidence/workbook parity ADRs were reviewed during continuation. This step remains a Google Sheets transport mirror hardening step only; it does not implement or claim the new evidence tab, bundled ledger evidence, official-layout parity gate, or offline/online single-builder parity contract.

The focused Google adapter suite passed with 131 tests after the remediation, and `uv run --no-sync -q python -m aeat.locales audit` passed across all locale catalogues.
