---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P09.S32'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P09.S32 - Verify registry workbook parity complexity baseline

Scope: execute the registry runtime decomposition step for workbook parity baseline verification.

## Description

- Measure `_workbook_parity.py` as the remaining workbook parity backend hotspot.
- Add a reviewability ratchet at the current reviewed baseline instead of changing workbook parity behavior.
- Preserve existing workbook parity public exports and runtime semantics.

## Outcome

- `_workbook_parity.py` remains unchanged at 1,336 lines.
- `test_registry_reviewability.py` now fails if `_workbook_parity.py` grows past the reviewed baseline.
- Future workbook parity decomposition must reduce or explicitly revise the baseline instead of allowing silent growth.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_registry_reviewability.py src/aeat/domain/calculations/registry/test_workbook_parity.py`
  - `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
  - `uv run --no-sync pytest -m workbook_parity src/aeat/domain/calculations/registry/test_workbook_parity.py::test_scan_workbook_discovers_xlsx_formula_cells src/aeat/domain/calculations/registry/test_workbook_parity.py::test_inventory_workbook_coverage_is_deterministic src/aeat/domain/calculations/registry/test_workbook_parity.py::test_inventory_workbook_coverage_reuses_unchanged_previous_report -q`
  - `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`
