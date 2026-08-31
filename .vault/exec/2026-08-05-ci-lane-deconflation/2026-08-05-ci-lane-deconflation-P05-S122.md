---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:82de237f273eef68c705ebff114caeac93b9090d4112f263257486b7439ff6df'
step_id: 'S122'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in calc_sheets_apply.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`

## Changes

- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `A` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_apply_adapter_helpers.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_integration.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_grid_resize.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py`
- `M` `src/cadrumo/tests/test_regulatory_cap_term_dominance.py`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/google/tests/test_apply_adapter_helpers.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_integration.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py src/cadrumo/adapters/outbound/google/tests/test_grid_resize.py` -> `pass (35 passed, exit 0)`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_typed_outcomes.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_preview.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_apply_no_empty_window.py` -> `pass (43 passed, exit 0)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/google/calc_sheets_apply.py src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py src/cadrumo/adapters/outbound/google/tests/test_apply_adapter_helpers.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_integration.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py src/cadrumo/adapters/outbound/google/tests/test_grid_resize.py src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py src/cadrumo/tests/test_regulatory_cap_term_dominance.py` -> `pass (exit 0)`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/adapters/outbound/google/calc_sheets_apply.py src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py src/cadrumo/adapters/outbound/google/tests/test_apply_adapter_helpers.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_integration.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py src/cadrumo/adapters/outbound/google/tests/test_grid_resize.py src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py src/cadrumo/tests/test_regulatory_cap_term_dominance.py` -> `pass (exit 0)`
- `verify:` `(Get-Content src/cadrumo/adapters/outbound/google/calc_sheets_apply.py | Measure-Object -Line).Lines` -> `pass (1028 <= 1250)`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/tests/test_regulatory_cap_term_dominance.py` -> `fail (2 unrelated relocation pairs, exit 1)`
- `verify:` `uv run --no-sync python -m dev.audit.size_budget` -> `fail (92 unrelated P05 findings, exit 1)`

## Notes

Grounded against predecessor `6df9635e34`. The corrected source measurement is 1,028 nonblank lines against the default 1,250-line limit; the size-budget script separately measures 1,172 physical lines and also confirms compliance. The original target measured 1,647 physical lines. The canonical global size gate exits 1 with 92 remaining findings owned by still-open P05 rows; `calc_sheets_apply.py` is absent from that output. The cap-term inventory now enrolls the moved Google Sheets pair at its canonical sibling path; its two remaining failures are six unrelated source/legacy-path relocation pairs. No baseline was changed.
