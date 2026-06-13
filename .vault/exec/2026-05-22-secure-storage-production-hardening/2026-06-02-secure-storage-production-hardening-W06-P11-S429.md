---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S429'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w06-p11-s429-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S429`

## Description

- Hardened strict `PullResult` metadata handling so a `MATCHES` verdict is not trusted without comparing actual metadata to the supplied registry snapshot.
- Extended pull coverage verification so registry SHA drift is detected with the other workbook identity coordinates.
- Reran registry-backed calc-sheets export/pull validation after the Modelo 202 registry blocker was fixed by `W06.P11.S435`.

## Outcome

Closed.

The S429 metadata strictness findings are resolved. The registry-backed roundtrip now executes against the committed registry instead of failing during Modelo 202 validation.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` passed 2 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py` passed 5 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_apply.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_calc_sheets_row_set_headers.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` passed 19 tests.
- `uv run --no-sync ruff check` passed for the touched calc-sheets and Modelo 202 registry test files.

## Notes

The prior S429 checkpoint was blocked by Modelo 202 registry defects. Those were tracked and resolved separately under `W06.P11.S435`; the adjacent relation-prefill all-or-nothing defect found while validating the same surface was tracked and resolved under `W06.P11.S436`.
